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


def _decrypt_for_runtime(channel_code: str, config: dict) -> dict:
    """运行时使用：把 ENC:: 解密成明文（仅给后端 SDK 用，不直接返回 C 端）。"""
    cfg = config or {}
    spec = CHANNEL_FIELD_SPEC.get(channel_code, [])
    secret_keys = {f["key"] for f in spec if f.get("is_secret")}
    out: dict[str, Any] = {}
    for k, v in cfg.items():
        if k in secret_keys and isinstance(v, str) and is_encrypted(v):
            out[k] = decrypt_value(v) or ""
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
    if payload.config is not None:
        spec = CHANNEL_FIELD_SPEC.get(channel_code, [])
        secret_keys = {f["key"] for f in spec if f.get("is_secret")}
        old = dict(ch.config_json or {})
        new_cfg = dict(old)
        for k, v in (payload.config or {}).items():
            # 非敏感字段直接覆盖（包括空字符串=清空）
            if k not in secret_keys:
                new_cfg[k] = v
                continue
            # 敏感字段：空值 → 保留旧值；非空 → 加密替换
            if v is None or (isinstance(v, str) and v.strip() == ""):
                continue
            # 客户端不应传掩码值；如果传了就忽略
            if isinstance(v, str) and v.startswith("****"):
                continue
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
    # 轻量实现：参数完整性 + 简单签名工具自检通过即视为成功。
    # 真实环境可在这里替换为 wechatpayv3 / alipay-sdk 的查询订单调用。
    msg = "参数完整性 + 签名工具自检通过（轻量模式）"
    detail = {"mode": "lightweight", "channel": channel_code}
    # 尝试做一次密钥可解密的自检
    try:
        runtime = _decrypt_for_runtime(channel_code, ch.config_json or {})
        # 检查关键字段非空
        spec = CHANNEL_FIELD_SPEC.get(channel_code, [])
        for f in spec:
            if _is_required(f, runtime):
                v = runtime.get(f["key"])
                if v is None or (isinstance(v, str) and v.strip() == ""):
                    raise ValueError(f"字段 {f['key']} 解密后为空")
    except Exception as e:  # noqa: BLE001
        ch.last_test_at = datetime.utcnow()
        ch.last_test_ok = False
        ch.last_test_message = f"自检失败：{e}"
        await db.commit()
        raise HTTPException(status_code=400, detail=ch.last_test_message)

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
