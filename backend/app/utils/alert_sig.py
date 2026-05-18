"""[PRD-FAMILY-GUARDIAN-V1] 公众号推送中转页（H5 alert-redirect）签名工具。

用途：
- 为公众号模板消息组装的中转页 URL 计算 HMAC-SHA256 签名（防越权 / 防伪造）
- 服务端在 click-tracking 接口侧校验签名

参与签名的字段（顺序固定）：
  log_id | member_id | report_id | t

签名算法：
  raw = f"logId={log_id}&memberId={member_id}&reportId={report_id}&t={t}"
  sig = hex( hmac_sha256(SECRET_KEY, raw) )[:16]   # 取前 16 位即可，长度足够

签名密钥：复用全局 settings.SECRET_KEY
"""

from __future__ import annotations

import hmac
import hashlib
from typing import Optional

from app.core.config import settings


def _build_raw(
    log_id: int,
    member_id: Optional[int],
    report_id: Optional[int],
    t: int,
) -> str:
    """构造参与签名的原文字符串。member_id/report_id 缺省时按 0 计算，确保稳定。"""
    return (
        f"logId={int(log_id)}"
        f"&memberId={int(member_id) if member_id else 0}"
        f"&reportId={int(report_id) if report_id else 0}"
        f"&t={int(t)}"
    )


def sign_alert_redirect(
    log_id: int,
    member_id: Optional[int],
    report_id: Optional[int],
    t: int,
    secret: Optional[str] = None,
) -> str:
    """生成 16 位 hex 签名。"""
    secret_bytes = (secret or settings.SECRET_KEY or "bini-health-default").encode("utf-8")
    raw = _build_raw(log_id, member_id, report_id, t)
    digest = hmac.new(secret_bytes, raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:16]


def verify_alert_redirect(
    log_id: int,
    member_id: Optional[int],
    report_id: Optional[int],
    t: int,
    sig: str,
    secret: Optional[str] = None,
) -> bool:
    """常量时间比较验签。"""
    if not sig:
        return False
    expected = sign_alert_redirect(log_id, member_id, report_id, t, secret=secret)
    try:
        return hmac.compare_digest(expected, sig.lower())
    except Exception:
        return False
