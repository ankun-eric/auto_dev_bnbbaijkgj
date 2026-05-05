"""[支付宝 H5 正式支付链路接入 v1.0]

支付宝服务层模块 — 统一负责：
1. 从「支付配置」表读取支付宝 H5 通道参数（AppID、私钥、公钥或证书三件套、access_mode）
2. 根据 access_mode 装配 python-alipay-sdk 客户端实例：
   - public_key 模式 → AliPay
   - cert 模式 → AliPayCert
3. 写死生产网关：https://openapi.alipay.com/gateway.do（用户已确认 4.B）
4. 提供高层方法：
   - create_wap_pay_url：调 alipay.trade.wap.pay 生成真实收银台 URL
   - verify_async_notify：异步通知 RSA2 验签
   - query_trade：查询订单（用于"测试按钮"和兜底对账）
5. 统一日志（含支付宝返回码、子码、子消息）

设计要点：
- 客户端按 channel_id 缓存（避免每次下单都重新解密私钥），管理端保存新配置时清缓存
- 网关写死生产，沙盒/排错时改源码（用户已确认选项 4.B）
- 测试桩兼容：当 python-alipay-sdk 未安装时，提供清晰的 ImportError 错误信息

Reference: PRD §4.2.2、§4.4
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Optional

logger = logging.getLogger(__name__)


ALIPAY_GATEWAY_PRODUCTION = "https://openapi.alipay.com/gateway.do"


# ─────────────── 客户端缓存（按 channel_id 维度） ───────────────
# key: channel_id (int)，value: {"version": int(updated_at timestamp), "client": AliPay/AliPayCert}
_CLIENT_CACHE: dict[int, dict[str, Any]] = {}


def _ts(dt) -> int:
    try:
        return int(dt.timestamp() * 1000) if dt else 0
    except Exception:  # noqa: BLE001
        return 0


def clear_alipay_client_cache(channel_id: Optional[int] = None) -> None:
    """管理端保存配置后调用，清缓存。channel_id=None 时清空全部。"""
    if channel_id is None:
        _CLIENT_CACHE.clear()
    else:
        _CLIENT_CACHE.pop(channel_id, None)


# ─────────────── 客户端构造 ───────────────


def _ensure_pem_format(key_text: str) -> str:
    """支付宝官方控制台可能给的是裸 base64 字符串（无 PEM 头尾）。
    SDK 兼容这两种，但我们统一兜底处理换行。
    """
    if not key_text:
        return key_text
    s = key_text.strip()
    # 已含 PEM 头：仅做换行统一
    if "BEGIN " in s and "END " in s:
        return s.replace("\r\n", "\n")
    # 裸 base64：返回原样（SDK 会包装）
    return s


def _write_temp_pem(content: str, suffix: str = ".crt") -> str:
    """把证书内容写到临时文件并返回路径。SDK 的 cert 模式只接收文件路径。"""
    fd, path = tempfile.mkstemp(prefix="alipay_", suffix=suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:  # noqa: BLE001
        os.close(fd)
        raise
    return path


def _build_client_from_config(channel_code: str, runtime_cfg: dict) -> Any:
    """根据「已解密」的 runtime config 装配 SDK 客户端。

    入参 runtime_cfg 必须为明文（即已经 _decrypt_for_runtime 过）：
      - app_id（必填）
      - access_mode：public_key / cert
      - app_private_key（必填）
      - public_key 模式：alipay_public_key
      - cert 模式：app_public_cert / alipay_root_cert / alipay_public_cert
    """
    try:
        from alipay import AliPay  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "未安装 python-alipay-sdk，无法发起真实支付宝调用；"
            "请在 backend 容器中安装：pip install python-alipay-sdk"
        ) from e

    app_id = (runtime_cfg.get("app_id") or "").strip()
    access_mode = (runtime_cfg.get("access_mode") or "public_key").strip()
    app_private_key_raw = _ensure_pem_format(runtime_cfg.get("app_private_key") or "")
    if not app_id or not app_private_key_raw:
        raise ValueError("支付宝配置缺失：app_id 或 app_private_key 为空")
    # [Bug 修复 2026-05-05] 运行时统一标准化为 PKCS#8 PEM，兼容历史脏数据
    # （PKCS#1 / 裸 base64 / 含 PEM 头的 PKCS#1 等），避免底层 cryptography
    # 抛 "RSA key format is not supported"。
    try:
        from app.utils.rsa_key import (
            normalize_rsa_private_key,
            InvalidRSAPrivateKeyError,
        )
        app_private_key = normalize_rsa_private_key(app_private_key_raw)
    except InvalidRSAPrivateKeyError as e:
        raise ValueError(
            f"数据库中保存的应用私钥格式无法识别（{e}），"
            "请到「管理后台 → 支付配置」重新填写 PKCS#8 格式的应用私钥"
        ) from e

    common_kwargs = dict(
        appid=app_id,
        app_notify_url=None,  # 每笔交易独立指定 notify_url
        app_private_key_string=app_private_key,
        sign_type="RSA2",
        debug=False,  # 写死生产
    )

    if access_mode == "cert":
        # 证书模式：python-alipay-sdk 3.3.0 以及 4.x 都没有独立 AliPayCert 类，
        # 而是通过 AliPay 类传入 app_alipay_public_cert_string / alipay_root_cert_string
        # / app_cert_public_key_string 实现。这里按 4.x 命名，3.x 单独 lazy import 兼容类。
        app_public_cert = runtime_cfg.get("app_public_cert") or ""
        alipay_root_cert = runtime_cfg.get("alipay_root_cert") or ""
        alipay_public_cert = runtime_cfg.get("alipay_public_cert") or ""
        if not app_public_cert or not alipay_root_cert or not alipay_public_cert:
            raise ValueError(
                "支付宝证书模式配置不完整：app_public_cert / "
                "alipay_root_cert / alipay_public_cert 三者必须齐全"
            )
        # 优先尝试 4.x 风格（直接通过 AliPay 传 cert string）
        try:
            client = AliPay(
                **common_kwargs,
                app_alipay_public_cert_string=alipay_public_cert,
                alipay_root_cert_string=alipay_root_cert,
                app_cert_public_key_string=app_public_cert,
            )
        except TypeError:
            # 3.x 兜底：尝试 lazy import 旧版可能存在的 AliPayCert
            try:
                from alipay import AliPayCert  # type: ignore
            except ImportError as e:
                raise RuntimeError(
                    "当前已安装的 python-alipay-sdk 版本不支持证书模式（"
                    "缺少 AliPayCert 或 cert 相关参数）；请升级到支持证书模式的版本，"
                    "或将『接入方式』切换为『公钥模式』。"
                ) from e
            app_public_cert_path = _write_temp_pem(app_public_cert, ".crt")
            alipay_root_cert_path = _write_temp_pem(alipay_root_cert, ".crt")
            alipay_public_cert_path = _write_temp_pem(alipay_public_cert, ".crt")
            client = AliPayCert(
                **common_kwargs,
                app_public_cert_path=app_public_cert_path,
                alipay_public_cert_path=alipay_public_cert_path,
                alipay_root_cert_path=alipay_root_cert_path,
            )
    else:
        # 公钥模式
        alipay_public_key = _ensure_pem_format(runtime_cfg.get("alipay_public_key") or "")
        if not alipay_public_key:
            raise ValueError("支付宝公钥模式配置不完整：alipay_public_key 为空")
        client = AliPay(
            **common_kwargs,
            alipay_public_key_string=alipay_public_key,
        )

    # 强制走生产网关
    try:
        # python-alipay-sdk 内部网关常量名为 _gateway 或 GATEWAY
        if hasattr(client, "_gateway"):
            client._gateway = ALIPAY_GATEWAY_PRODUCTION
    except Exception:  # noqa: BLE001
        pass
    return client


async def get_alipay_client_for_channel(db, channel_code: str = "alipay_h5"):
    """从 DB 取通道、解密敏感字段、装配并缓存 SDK 客户端，返回 (client, channel)。"""
    from sqlalchemy import select
    from app.models.models import PaymentChannel
    from app.api.payment_config import _decrypt_for_runtime

    res = await db.execute(
        select(PaymentChannel).where(PaymentChannel.channel_code == channel_code)
    )
    ch = res.scalar_one_or_none()
    if ch is None:
        raise ValueError(f"未找到支付通道：{channel_code}")
    if not ch.is_complete:
        raise ValueError(f"支付通道 {channel_code} 配置不完整")

    cache_entry = _CLIENT_CACHE.get(ch.id)
    cur_version = _ts(ch.updated_at)
    if cache_entry and cache_entry.get("version") == cur_version:
        return cache_entry["client"], ch

    runtime_cfg = _decrypt_for_runtime(channel_code, ch.config_json or {})
    client = _build_client_from_config(channel_code, runtime_cfg)
    _CLIENT_CACHE[ch.id] = {"version": cur_version, "client": client}
    return client, ch


# ─────────────── 高层方法 ───────────────


def create_wap_pay_url(
    client: Any,
    *,
    out_trade_no: str,
    total_amount: float,
    subject: str,
    return_url: str,
    notify_url: str,
    time_expire: Optional[str] = None,
    timeout_express: Optional[str] = "30m",
) -> str:
    """调用 alipay.trade.wap.pay 生成真实收银台跳转 URL。

    `time_expire`：订单绝对超时时间字符串，格式 "yyyy-MM-dd HH:mm:ss"（北京时间）；
    `timeout_express`：订单相对超时（兜底，30m）。

    返回完整 URL：https://openapi.alipay.com/gateway.do?...
    """
    biz_content: dict[str, Any] = {
        "out_trade_no": out_trade_no,
        "product_code": "QUICK_WAP_WAY",
        "total_amount": f"{float(total_amount):.2f}",
        "subject": (subject or "订单")[:256],
        "quit_url": return_url,
    }
    if time_expire:
        biz_content["time_expire"] = time_expire
    elif timeout_express:
        biz_content["timeout_express"] = timeout_express

    # python-alipay-sdk: api_alipay_trade_wap_pay 返回的是查询字符串（不含网关前缀）
    qs = client.api_alipay_trade_wap_pay(
        out_trade_no=out_trade_no,
        total_amount=f"{float(total_amount):.2f}",
        subject=(subject or "订单")[:256],
        return_url=return_url,
        notify_url=notify_url,
        timeout_express=biz_content.get("timeout_express"),
        time_expire=biz_content.get("time_expire"),
    )
    if not qs:
        raise RuntimeError("支付宝返回空 URL")
    if qs.startswith("http://") or qs.startswith("https://"):
        return qs
    sep = "?" if "?" not in ALIPAY_GATEWAY_PRODUCTION else "&"
    return f"{ALIPAY_GATEWAY_PRODUCTION}{sep}{qs}"


def verify_async_notify(client: Any, form_dict: dict) -> bool:
    """对支付宝异步通知做 RSA2 验签。

    form_dict 必须为原始 form 表单（保留 sign / sign_type 字段且不修改大小写/顺序）。
    成功返回 True；失败返回 False（同时打 warning 日志）。
    """
    if not form_dict:
        return False
    sign = form_dict.get("sign")
    if not sign:
        logger.warning("alipay async notify missing 'sign' field")
        return False
    payload = {k: v for k, v in form_dict.items() if k not in ("sign", "sign_type")}
    try:
        ok = client.verify(payload, sign)
        if not ok:
            logger.warning("alipay async notify verify FAILED, payload keys=%s",
                           list(payload.keys()))
        return bool(ok)
    except Exception as e:  # noqa: BLE001
        logger.error("alipay async notify verify exception: %s", e)
        return False


def query_trade(client: Any, out_trade_no: str) -> dict:
    """查询订单（alipay.trade.query），返回支付宝响应 dict。

    用于：
      a) 测试按钮：传一个绝不可能存在的订单号，期望得到 ACQ.TRADE_NOT_EXIST
      b) 异步通知后兜底对账（本期未启用）
    """
    try:
        resp = client.api_alipay_trade_query(out_trade_no=out_trade_no)
    except Exception as e:  # noqa: BLE001
        logger.error("alipay_service query_trade exception: %s", e)
        raise
    if isinstance(resp, dict):
        return resp
    return {"raw": str(resp)}


# ─────────────── 测试按钮：连通性 + 参数正确性判定 ───────────────


def interpret_test_query_response(resp: dict) -> tuple[bool, str, dict]:
    """根据 query_trade 返回，判定测试按钮的成功/失败 + 友好文案。

    成功判据（PRD §4.2.6）：
      code=10000, sub_code=ACQ.TRADE_NOT_EXIST → ✅ 测试通过

    失败友好映射：
      ISV.INVALID_SIGNATURE → "签名校验失败，请检查应用私钥/支付宝公钥是否一一对应"
      ACQ.INVALID_PARAMETER / INVALID_PARAMETER → "参数错（多为 AppID/私钥不匹配或时间偏移）"
      其他 → 透传 sub_code + sub_msg
    """
    detail = dict(resp or {})
    code = str(resp.get("code", ""))
    sub_code = str(resp.get("sub_code", ""))
    sub_msg = str(resp.get("sub_msg", ""))
    msg = str(resp.get("msg", ""))

    if code == "10000":
        # 不期望真的查到，但万一查到了也算通了
        return True, f"测试通过（{msg or 'Success'}）", detail

    # 业务错误（code != 10000），看 sub_code
    if sub_code == "ACQ.TRADE_NOT_EXIST":
        return True, "测试通过：参数正确、网络连通、签名/验签正常", detail

    if sub_code in ("ISV.INVALID_SIGNATURE", "INVALID_SIGNATURE"):
        return False, "签名校验失败，请检查应用私钥/支付宝公钥是否一一对应", detail
    if sub_code in ("ACQ.INVALID_PARAMETER", "INVALID_PARAMETER", "ALIPAY_PUBLIC_KEY_ERROR"):
        return False, f"参数错（{sub_code}）：AppID 与私钥可能不匹配，{sub_msg}", detail
    if sub_code in ("ISV.WRONG_AUTH_APP_ID", "ACQ.SYSTEM_ERROR"):
        return False, f"AppID 与配置不匹配（{sub_code}）：{sub_msg}", detail

    # 其它未知 sub_code，透传
    return False, f"支付宝返回错误：{sub_code or msg or '未知错误'} - {sub_msg}", detail
