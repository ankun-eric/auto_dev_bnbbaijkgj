"""[支付配置 PRD v1.0] 管理后台支付通道配置接口。

接口列表：
- GET    /api/admin/payment-channels                列表（含掩码）
- GET    /api/admin/payment-channels/{code}         单条详情（含掩码）
- PUT    /api/admin/payment-channels/{code}         更新（敏感字段空值保留旧值；新值加密）
- PATCH  /api/admin/payment-channels/{code}/toggle  启用/禁用（未配置完整时拒绝启用）
- POST   /api/admin/payment-channels/{code}/test    测试连接（轻量自检）
- GET    /api/admin/payment-channels/{code}/default-notify-url  默认 notify URL

权限：本期使用 admin 角色（项目暂未细分 super_admin），等价语义：仅后台管理员可访问。
"""
from __future__ import annotations

import logging
import os
import traceback
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_role
from app.models.models import PaymentChannel
from app.schemas.payment_config import (
    DefaultNotifyUrlResponse,
    PaymentChannelListItem,
    PaymentChannelResponse,
    PaymentChannelToggleRequest,
    PaymentChannelUpdate,
    PaymentTestResult,
)
from app.utils.crypto import (
    ENC_PREFIX,
    DecryptionError,
    decrypt_value,
    encrypt_value,
    is_encrypted,
    mask_secret,
    mask_value,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/payment-channels", tags=["支付配置"])

admin_dep = require_role("admin")


# ──────────────── 字段元数据 ────────────────

# 每通道字段定义：(key, label, is_secret, required_for=[modes])
# is_secret=True 的字段会用 AES-256-GCM 加密存储；
# is_secret=False 的字段也会做尾 4 位掩码以减少泄露风险。

WECHAT_COMMON_FIELDS = [
    {"key": "mch_id", "label": "商户号", "is_secret": False, "required": True},
    {"key": "api_v3_key", "label": "API V3 密钥", "is_secret": True, "required": True},
    {"key": "cert_serial_no", "label": "商户证书序列号", "is_secret": False, "required": True},
    {"key": "private_key", "label": "商户私钥（PEM）", "is_secret": True, "required": True},
]

CHANNEL_FIELD_SPEC: dict[str, list[dict]] = {
    "wechat_miniprogram": [
        {"key": "appid", "label": "小程序 AppID", "is_secret": False, "required": True},
        *WECHAT_COMMON_FIELDS,
    ],
    "wechat_app": [
        {"key": "app_id", "label": "开放平台 AppID", "is_secret": False, "required": True},
        *WECHAT_COMMON_FIELDS,
    ],
    "alipay_h5": [
        {"key": "app_id", "label": "应用 AppID", "is_secret": False, "required": True},
        {"key": "access_mode", "label": "接入模式", "is_secret": False, "required": True,
         "enum": ["public_key", "cert"]},
        {"key": "app_private_key", "label": "应用私钥（PEM）", "is_secret": True,
         "required_when": "always"},
        {"key": "alipay_public_key", "label": "支付宝公钥", "is_secret": True,
         "required_when": ("access_mode", "public_key")},
        {"key": "app_public_cert", "label": "应用公钥证书", "is_secret": True,
         "required_when": ("access_mode", "cert")},
        {"key": "alipay_root_cert", "label": "支付宝根证书", "is_secret": True,
         "required_when": ("access_mode", "cert")},
        {"key": "alipay_public_cert", "label": "支付宝公钥证书", "is_secret": True,
         "required_when": ("access_mode", "cert")},
    ],
    "alipay_app": [
        {"key": "app_id", "label": "应用 AppID", "is_secret": False, "required": True},
        {"key": "access_mode", "label": "接入模式", "is_secret": False, "required": True,
         "enum": ["public_key", "cert"]},
        {"key": "app_private_key", "label": "应用私钥（PEM）", "is_secret": True,
         "required_when": "always"},
        {"key": "alipay_public_key", "label": "支付宝公钥", "is_secret": True,
         "required_when": ("access_mode", "public_key")},
        {"key": "app_public_cert", "label": "应用公钥证书", "is_secret": True,
         "required_when": ("access_mode", "cert")},
        {"key": "alipay_root_cert", "label": "支付宝根证书", "is_secret": True,
         "required_when": ("access_mode", "cert")},
        {"key": "alipay_public_cert", "label": "支付宝公钥证书", "is_secret": True,
         "required_when": ("access_mode", "cert")},
    ],
}


# 4 通道初始化种子（schema_sync 也会用到）
DEFAULT_CHANNELS = [
    {"channel_code": "wechat_miniprogram", "channel_name": "微信小程序支付",
     "display_name": "微信支付", "platform": "miniprogram", "provider": "wechat", "sort_order": 10},
    {"channel_code": "wechat_app", "channel_name": "微信APP支付",
     "display_name": "微信支付", "platform": "app", "provider": "wechat", "sort_order": 10},
    {"channel_code": "alipay_h5", "channel_name": "支付宝H5支付",
     "display_name": "支付宝", "platform": "h5", "provider": "alipay", "sort_order": 10},
    {"channel_code": "alipay_app", "channel_name": "支付宝APP支付",
     "display_name": "支付宝", "platform": "app", "provider": "alipay", "sort_order": 20},
]


PLATFORM_LABEL_MAP = {
    "wechat_miniprogram": "小程序",
    "wechat_app": "APP",
    "alipay_h5": "H5",
    "alipay_app": "APP",
}


# ──────────────── 配置完整性 + 序列化辅助 ────────────────


def _is_required(field_def: dict, config: dict) -> bool:
    """根据 field_def 判断当前 config 下该字段是否必填。"""
    if field_def.get("required"):
        return True
    rw = field_def.get("required_when")
    if rw is None:
        return False
    if rw == "always":
        return True
    if isinstance(rw, tuple) and len(rw) == 2:
        ref_key, ref_val = rw
        return (config or {}).get(ref_key) == ref_val
    return False


def check_completeness(channel_code: str, config: dict) -> tuple[bool, list[str]]:
    """返回 (is_complete, missing_field_keys)。"""
    spec = CHANNEL_FIELD_SPEC.get(channel_code, [])
    missing: list[str] = []
    cfg = config or {}
    for f in spec:
        if not _is_required(f, cfg):
            continue
        v = cfg.get(f["key"])
        if v is None or (isinstance(v, str) and v.strip() == ""):
            missing.append(f["key"])
    return (len(missing) == 0), missing


def _build_masked_config(channel_code: str, config: dict) -> dict:
    """生成"已掩码"的 config 视图：

    - 敏感字段：显示为 mask_secret(stored_value)（解密 + 末 4 位）
    - 非敏感字段：显示 mask_value(原文)
    - 未配置（None / 空字符串）：显示空字符串
    """
    spec = CHANNEL_FIELD_SPEC.get(channel_code, [])
    cfg = config or {}
    out: dict[str, Any] = {}
    for f in spec:
        k = f["key"]
        v = cfg.get(k)
        if v is None or v == "":
            out[k] = ""
            continue
        if f.get("is_secret"):
            out[k] = mask_secret(v)
        else:
            # access_mode 这种枚举字段直接展示
            if f.get("enum"):
                out[k] = str(v)
            else:
                out[k] = mask_value(str(v))
    return out


def _decrypt_for_runtime(
    channel_code: str, config: dict, *, raise_on_error: bool = False
) -> dict:
    """运行时使用：把 ENC:: 解密成明文（仅给后端 SDK 用，不直接返回 C 端）。

    [Bug 修复 2026-05-05] 新增 ``raise_on_error`` 参数：当为 True 时，
    单字段解密失败会向上抛 ``DecryptionError``，便于"测试连接"接口区分
    "密钥被改导致解密失败" 与 "字段本身就是空" 这两种错因。
    """
    cfg = config or {}
    spec = CHANNEL_FIELD_SPEC.get(channel_code, [])
    secret_keys = {f["key"] for f in spec if f.get("is_secret")}
    out: dict[str, Any] = {}
    for k, v in cfg.items():
        if k in secret_keys and isinstance(v, str) and is_encrypted(v):
            out[k] = decrypt_value(v, raise_on_error=raise_on_error) or ""
        else:
            out[k] = v
    return out


def _serialize_channel(ch: PaymentChannel) -> PaymentChannelResponse:
    """构造单条通道响应。

    [Bug 修复] 对 created_at / updated_at 做 None 兜底，避免历史种子数据
    缺失时间戳直接让接口 500。
    [Bug 修复] config_masked 单字段失败降级为 ``****``，不让单条字段坏掉
    整条列表。
    """
    now = datetime.utcnow()
    try:
        masked = _build_masked_config(ch.channel_code, ch.config_json or {})
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "payment_config build_masked_config failed for %s: %s",
            ch.channel_code, e,
        )
        # 全字段降级
        spec = CHANNEL_FIELD_SPEC.get(ch.channel_code, [])
        masked = {f["key"]: "****" for f in spec}
    return PaymentChannelResponse(
        id=ch.id,
        channel_code=ch.channel_code,
        channel_name=ch.channel_name,
        display_name=ch.display_name,
        platform=ch.platform,
        provider=ch.provider,
        is_enabled=bool(ch.is_enabled),
        is_complete=bool(ch.is_complete),
        notify_url=ch.notify_url,
        return_url=ch.return_url,
        sort_order=ch.sort_order or 0,
        config_masked=masked,
        last_test_at=ch.last_test_at,
        last_test_ok=ch.last_test_ok,
        last_test_message=ch.last_test_message,
        created_at=ch.created_at or now,
        updated_at=ch.updated_at or now,
    )


def _safe_serialize_channel(
    ch: PaymentChannel,
) -> Optional[PaymentChannelResponse]:
    """单条记录序列化失败时返回占位响应（不让列表整体挂掉）。"""
    try:
        return _serialize_channel(ch)
    except Exception as e:  # noqa: BLE001
        logger.error(
            "payment_config serialize failed for %s: %s\n%s",
            getattr(ch, "channel_code", "<unknown>"), e, traceback.format_exc(),
        )
        try:
            now = datetime.utcnow()
            return PaymentChannelResponse(
                id=ch.id or 0,
                channel_code=ch.channel_code or "unknown",
                channel_name=ch.channel_name or "未知通道",
                display_name=ch.display_name or "未知通道",
                platform=ch.platform or "unknown",
                provider=ch.provider or "unknown",
                is_enabled=False,
                is_complete=False,
                notify_url=None,
                return_url=None,
                sort_order=0,
                config_masked={},
                last_test_at=None,
                last_test_ok=False,
                last_test_message=f"通道数据异常：{e}",
                created_at=now,
                updated_at=now,
            )
        except Exception:  # noqa: BLE001
            return None


def _build_default_notify_url(request: Request, channel_code: str) -> str:
    """基于当前请求 base_url 构造默认 notify URL。"""
    # 优先使用环境变量配置的对外 base_url（部署到 /autodev/<deploy_id>/api 子路径下时必需）
    base = os.environ.get("PUBLIC_API_BASE_URL", "").rstrip("/")
    if not base:
        # 退回 request.base_url，并去除末尾斜杠
        base = str(request.base_url).rstrip("/")
    return f"{base}/api/pay/notify/{channel_code}"


# ──────────────── 接口实现 ────────────────


@router.get("", response_model=list[PaymentChannelResponse])
async def list_payment_channels(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(admin_dep),
):
    """[Bug 修复] 全局异常兜底，返回结构化 detail 方便前端展示。

    单条记录序列化失败时降级为占位记录，不让整条列表挂掉。
    缺失的初始通道在请求时尝试自动补齐（保证后续启动也能自愈）。
    """
    try:
        # 自愈：缺通道时自动补齐
        try:
            await _ensure_default_channels(db)
        except Exception as e:  # noqa: BLE001
            logger.warning("payment_config ensure default channels failed: %s", e)

        res = await db.execute(
            select(PaymentChannel).order_by(
                PaymentChannel.platform, PaymentChannel.sort_order,
            )
        )
        rows = res.scalars().all()
        results: list[PaymentChannelResponse] = []
        for ch in rows:
            item = _safe_serialize_channel(ch)
            if item is not None:
                results.append(item)
        return results
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(
            "payment_config list failed: %s\n%s", e, traceback.format_exc(),
        )
        raise HTTPException(
            status_code=500,
            detail=f"支付通道列表加载失败：{type(e).__name__}: {e}",
        )


async def _ensure_default_channels(db: AsyncSession) -> int:
    """[Bug 修复 FIX-1] 在请求时检查 4 条通道是否齐全，缺失则补齐。

    幂等：已存在的不会被覆盖，返回新增条数。
    """
    res = await db.execute(select(PaymentChannel.channel_code))
    existing = {r[0] for r in res.all()}
    inserted = 0
    now = datetime.utcnow()
    for ch in DEFAULT_CHANNELS:
        if ch["channel_code"] in existing:
            continue
        new_ch = PaymentChannel(
            channel_code=ch["channel_code"],
            channel_name=ch["channel_name"],
            display_name=ch["display_name"],
            platform=ch["platform"],
            provider=ch["provider"],
            is_enabled=False,
            is_complete=False,
            sort_order=ch["sort_order"],
            config_json={},
            created_at=now,
            updated_at=now,
        )
        db.add(new_ch)
        inserted += 1
    if inserted:
        await db.commit()
    return inserted


@router.get("/{channel_code}", response_model=PaymentChannelResponse)
async def get_payment_channel(
    channel_code: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(admin_dep),
):
    res = await db.execute(select(PaymentChannel).where(PaymentChannel.channel_code == channel_code))
    ch = res.scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="支付通道不存在")
    return _serialize_channel(ch)


@router.put("/{channel_code}", response_model=PaymentChannelResponse)
async def update_payment_channel(
    channel_code: str,
    payload: PaymentChannelUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(admin_dep),
):
    res = await db.execute(select(PaymentChannel).where(PaymentChannel.channel_code == channel_code))
    ch = res.scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="支付通道不存在")

    # 显示名称必填校验（若提交了 display_name 则不能为空字符串）
    if payload.display_name is not None:
        if payload.display_name.strip() == "":
            raise HTTPException(status_code=400, detail="显示名称不能为空")
        ch.display_name = payload.display_name.strip()
    if payload.notify_url is not None:
        ch.notify_url = payload.notify_url.strip() or None
    if payload.return_url is not None:
        ch.return_url = payload.return_url.strip() or None
    if payload.sort_order is not None:
        ch.sort_order = int(payload.sort_order)

    # config 合并：保留旧值；敏感字段空值时保留旧值，非空值则加密替换
    # [Bug 修复 2026-05-05] 首次创建场景下，必填敏感字段为空值时强制 422 拒绝，
    # 避免静默吞掉私钥导致后续测试连接出现"解密后为空"的误导性报错。
    if payload.config is not None:
        spec = CHANNEL_FIELD_SPEC.get(channel_code, [])
        secret_keys = {f["key"] for f in spec if f.get("is_secret")}
        spec_by_key = {f["key"]: f for f in spec}
        old = dict(ch.config_json or {})
        new_cfg = dict(old)
        # 用于"该字段当前是否必填"判断的合并视图：旧值 + 本次提交的非敏感字段
        # （比如 access_mode 切换会影响哪些证书字段是必填）
        merged_for_required: dict[str, Any] = dict(old)
        for k, v in (payload.config or {}).items():
            if k not in secret_keys:
                merged_for_required[k] = v
        for k, v in (payload.config or {}).items():
            # 非敏感字段直接覆盖（包括空字符串=清空）
            if k not in secret_keys:
                new_cfg[k] = v
                continue

            is_blank = v is None or (isinstance(v, str) and v.strip() == "")
            is_mask = isinstance(v, str) and v.startswith("****")

            if is_blank:
                # 关键判断：DB 中是否已经有该字段的密文？
                old_val = old.get(k)
                had_old_value = isinstance(old_val, str) and (
                    old_val.startswith(ENC_PREFIX) or old_val.strip() != ""
                )
                if not had_old_value:
                    # 首次创建场景：检查该字段是否必填
                    field_def = spec_by_key.get(k)
                    if field_def and _is_required(field_def, merged_for_required):
                        raise HTTPException(
                            status_code=422,
                            detail=(
                                f"敏感字段 {field_def.get('label', k)} "
                                f"首次创建时不能为空，请填写后再保存"
                            ),
                        )
                # 编辑场景下，留空 = 保留旧值
                continue

            # 客户端不应传掩码值；如果传了就忽略，保留旧值
            if is_mask:
                continue

            # [Bug 修复 2026-05-05] 支付宝通道 app_private_key 字段在落库前
            # 必须先做格式校验 + PKCS#8 标准化，避免静默存入 PKCS#1 私钥
            # 导致后续测试连接时抛 "RSA key format is not supported"。
            if (
                k == "app_private_key"
                and channel_code in ("alipay_h5", "alipay_app")
            ):
                try:
                    from app.utils.rsa_key import validate_rsa_private_key
                except Exception:  # noqa: BLE001
                    validate_rsa_private_key = None  # type: ignore
                if validate_rsa_private_key is not None:
                    ok, normalized, reason = validate_rsa_private_key(str(v))
                    if not ok:
                        raise HTTPException(status_code=422, detail=reason)
                    # 用标准化后的 PKCS#8 PEM 入库（同一份私钥，仅格式归一）
                    v = normalized

            new_cfg[k] = encrypt_value(str(v))
        # 完整性重算
        # 校验完整性时使用"是否填充"（敏感字段填充以 ENC:: 起头亦视作已填）
        is_complete, _missing = check_completeness(channel_code, new_cfg)
        ch.config_json = new_cfg
        ch.is_complete = is_complete
        # 如果配置变得不完整，自动禁用
        if not is_complete:
            ch.is_enabled = False
    ch.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(ch)
    # [支付宝 H5 正式接入 v1.0] 配置保存后清缓存，下一次调用强制重建客户端
    if (ch.provider or "").lower() == "alipay":
        try:
            from app.services.alipay_service import clear_alipay_client_cache
            clear_alipay_client_cache(ch.id)
        except Exception:  # noqa: BLE001
            pass
    return _serialize_channel(ch)


@router.patch("/{channel_code}/toggle", response_model=PaymentChannelResponse)
async def toggle_payment_channel(
    channel_code: str,
    payload: PaymentChannelToggleRequest,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(admin_dep),
):
    res = await db.execute(select(PaymentChannel).where(PaymentChannel.channel_code == channel_code))
    ch = res.scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="支付通道不存在")
    if payload.enabled and not ch.is_complete:
        raise HTTPException(status_code=400, detail="配置不完整，无法启用，请先完成必填字段")
    ch.is_enabled = bool(payload.enabled)
    ch.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(ch)
    return _serialize_channel(ch)


@router.post("/{channel_code}/test", response_model=PaymentTestResult)
async def test_payment_channel(
    channel_code: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(admin_dep),
):
    """[支付宝 H5 正式接入 v1.0 · §4.2.6 测试按钮升级]

    对支付宝通道（alipay_h5 / alipay_app）：
      - 实装 SDK 客户端 + 调用 alipay.trade.query 查询一个绝不可能存在的订单号
      - code=10000 / sub_code=ACQ.TRADE_NOT_EXIST → 测试通过
      - 其它 sub_code → 友好文案
      - 网络异常 → "网络不通" 文案

    对其它通道（wechat_*）：保留原"参数完整性 + 解密自检"轻量模式（不在本期范围）。
    """
    import uuid as _uuid

    res = await db.execute(select(PaymentChannel).where(PaymentChannel.channel_code == channel_code))
    ch = res.scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="支付通道不存在")
    is_complete, missing = check_completeness(channel_code, ch.config_json or {})
    if not is_complete:
        raise HTTPException(
            status_code=400,
            detail=f"配置不完整：缺少字段 {', '.join(missing)}",
        )

    # —— 解密自检（公共前置） ——
    # [Bug 修复 2026-05-05] 区分"密钥不一致" 与 "字段未保存"两种错因：
    #   - DecryptionError → 提示运维核对 PAYMENT_CONFIG_ENCRYPTION_KEY
    #   - 解密成功但是空 → 提示重新填写并保存（敏感字段在 DB 里根本不存在）
    try:
        runtime = _decrypt_for_runtime(
            channel_code, ch.config_json or {}, raise_on_error=True
        )
        spec = CHANNEL_FIELD_SPEC.get(channel_code, [])
        cfg_raw = ch.config_json or {}
        for f in spec:
            if _is_required(f, runtime):
                key = f["key"]
                label = f.get("label", key)
                v = runtime.get(key)
                if v is None or (isinstance(v, str) and v.strip() == ""):
                    raw_v = cfg_raw.get(key)
                    if raw_v is None or (isinstance(raw_v, str) and raw_v.strip() == ""):
                        raise ValueError(
                            f"字段 {label} 在数据库中不存在或为空，请重新填写并保存"
                        )
                    raise ValueError(f"字段 {label} 解密后为空")
    except DecryptionError as e:
        ch.last_test_at = datetime.utcnow()
        ch.last_test_ok = False
        ch.last_test_message = (
            f"自检失败：解密失败，可能是 PAYMENT_CONFIG_ENCRYPTION_KEY 被更换过（{e}）"
        )
        await db.commit()
        raise HTTPException(status_code=400, detail=ch.last_test_message)
    except Exception as e:  # noqa: BLE001
        ch.last_test_at = datetime.utcnow()
        ch.last_test_ok = False
        ch.last_test_message = f"自检失败：{e}"
        await db.commit()
        raise HTTPException(status_code=400, detail=ch.last_test_message)

    # —— 支付宝通道走真实 query 联通性测试 ——
    if (ch.provider or "").lower() == "alipay":
        try:
            from app.services.alipay_service import (
                _build_client_from_config,
                interpret_test_query_response,
                query_trade,
                clear_alipay_client_cache,
            )
        except ImportError as e:  # 依赖未装：明确告知
            ch.last_test_at = datetime.utcnow()
            ch.last_test_ok = False
            ch.last_test_message = f"支付宝 SDK 未安装：{e}"
            await db.commit()
            raise HTTPException(status_code=400, detail=ch.last_test_message)

        try:
            client = _build_client_from_config(channel_code, runtime)
            test_no = f"__health_test_{_uuid.uuid4().hex[:16]}"
            resp = query_trade(client, test_no)
            ok, message, raw_detail = interpret_test_query_response(resp)
            # 配置变更后清缓存（防止用旧客户端）
            clear_alipay_client_cache(ch.id)
        except Exception as e:  # noqa: BLE001
            err_text = str(e)
            lower = err_text.lower()
            # [Bug 修复 2026-05-05] _build_client_from_config 在 alipay SDK
            # 未安装时会抛 RuntimeError("未安装 python-alipay-sdk...")，
            # 这里识别后给出与 ImportError 同样明确的提示。
            if "python-alipay-sdk" in err_text or "未安装" in err_text:
                ch.last_test_at = datetime.utcnow()
                ch.last_test_ok = False
                ch.last_test_message = f"支付宝 SDK 未安装：{err_text}"
                await db.commit()
                raise HTTPException(status_code=400, detail=ch.last_test_message)
            if (
                "timed out" in lower
                or "timeout" in lower
                or "name or service not known" in lower
                or "network is unreachable" in lower
                or "connection refused" in lower
                or "failed to establish a new connection" in lower
            ):
                friendly = "网络不通：无法连接支付宝网关，请检查出网/防火墙"
            elif (
                "rsa key format is not supported" in lower
                or "could not deserialize key data" in lower
                or "unsupported" in lower and "key" in lower
                or "格式无法识别" in err_text
                or "格式不被支持" in err_text
            ):
                friendly = (
                    "「应用私钥」格式不被支持。请使用支付宝开放平台「密钥工具」"
                    "生成的「应用私钥PKCS8.txt」文件中的内容"
                    "（注意：不是「应用私钥RSA2048.txt」）。"
                    "点击「保存」后再点「测试」即可。"
                )
            else:
                friendly = f"调用支付宝异常：{err_text}"
            ch.last_test_at = datetime.utcnow()
            ch.last_test_ok = False
            ch.last_test_message = friendly
            await db.commit()
            raise HTTPException(status_code=400, detail=friendly)

        ch.last_test_at = datetime.utcnow()
        ch.last_test_ok = bool(ok)
        ch.last_test_message = message
        await db.commit()
        if not ok:
            raise HTTPException(status_code=400, detail=message)
        return PaymentTestResult(
            success=True,
            message=message,
            detail={"mode": "alipay_real_query", "channel": channel_code, "raw": raw_detail},
        )

    # —— 非支付宝通道：保留原轻量模式 ——
    msg = "参数完整性 + 签名工具自检通过（轻量模式）"
    detail = {"mode": "lightweight", "channel": channel_code}
    ch.last_test_at = datetime.utcnow()
    ch.last_test_ok = True
    ch.last_test_message = msg
    await db.commit()
    return PaymentTestResult(success=True, message=msg, detail=detail)


@router.get("/{channel_code}/default-notify-url", response_model=DefaultNotifyUrlResponse)
async def default_notify_url(
    channel_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(admin_dep),
):
    # 仅校验存在性
    res = await db.execute(select(PaymentChannel).where(PaymentChannel.channel_code == channel_code))
    ch = res.scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="支付通道不存在")
    return DefaultNotifyUrlResponse(notify_url=_build_default_notify_url(request, channel_code))
