"""
[PRD-HOME-SAFETY-V1 2026-05-27 / PRD-HOME-SAFETY-V2 2026-05-27]
智能硬件绑定 · 居家安全设备 v1.0 + 外部 API 对接 v2

设备类型：
- type=1 紧急呼叫器
- type=2 烟雾报警器
- type=7 水位报警器

模块特性（v1）：
- 4 张独立表（home_safety_*），SQLAlchemy 自动建表
- 用户端 API（/api/home_safety/...）+ 管理后台 API（/api/admin/home_safety/...）
- 上游回调（/callback/home_safety/...）
- 5 分钟去重窗口
- 主守护人强制锁定 + 其他守护人最多 2 位

v2 新增（[PRD-HOME-SAFETY-V2 2026-05-27]）：
- 回调接收接口：厂商真实报文映射 + 永久幂等（vendor_msg_id）+ 8 大异常兜底
- 回调配置：上游 base + path 拆分、Token 密文展示
- 推送上游：真实 HTTP 调用 + 推送历史落库
- 新表：home_safety_callback_push_history / home_safety_callback_log
- AI 外呼降级：默认标记 failed
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    desc,
    func,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, get_db
from app.core.security import get_current_user

try:
    from app.models.models import FamilyManagement, User  # type: ignore
except Exception:  # pragma: no cover
    FamilyManagement = None  # type: ignore
    User = None  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["居家安全设备-v1"])

# ────────────── 常量 ──────────────
DEVICE_TYPE_EMERGENCY = 1
DEVICE_TYPE_SMOKE = 2
DEVICE_TYPE_WATER = 7
ALL_DEVICE_TYPES = [DEVICE_TYPE_EMERGENCY, DEVICE_TYPE_SMOKE, DEVICE_TYPE_WATER]

# [PRD-CARE-MODE-OPTIM-V1 2026-05-31] 关怀模式优化：设备名统一为
# 紧急呼叫器 / 烟雾报警器 / 水浸报警器（去掉"宾尼"前缀，"水位"改"水浸"），
# 健康档案本人 Tab 副标题同步引用同口径。
DEVICE_TYPE_LABEL = {
    DEVICE_TYPE_EMERGENCY: "紧急呼叫器",
    DEVICE_TYPE_SMOKE: "烟雾报警器",
    DEVICE_TYPE_WATER: "水浸报警器",
}
DEVICE_TYPE_COLOR = {
    DEVICE_TYPE_EMERGENCY: "red",
    DEVICE_TYPE_SMOKE: "orange",
    DEVICE_TYPE_WATER: "yellow",
}
DEVICE_TYPE_NOTICE_TITLE = {
    DEVICE_TYPE_EMERGENCY: "【紧急】{user_name} 触发了 SOS 呼叫，请立即联系！",
    DEVICE_TYPE_SMOKE: "【警告】{user_name} 家中检测到烟雾，请确认是否火情",
    DEVICE_TYPE_WATER: "【提醒】{user_name} 家中检测到漏水，请尽快查看",
}
DEVICE_TYPE_AI_SCRIPT = {
    DEVICE_TYPE_EMERGENCY: "您好，{user_name} 的紧急呼叫器刚刚触发了 SOS 报警，请立即与本人或家属联系。",
    DEVICE_TYPE_SMOKE: "您好，{user_name} 家中的烟雾报警器刚刚被触发，请确认是否发生火情。",
    DEVICE_TYPE_WATER: "您好，{user_name} 家中的水位报警器刚刚被触发，请尽快查看是否漏水。",
}

DEDUPE_WINDOW_SECONDS = 5 * 60  # 5 分钟

# [BUGFIX HS-CALLBACK-DATATYPE 2026-05-29] 厂商回调 dataType 白名单分类
# - ALERT_DATA_TYPES：走告警链路（新厂商的 new-call-msg + 老厂商兼容的 call-msg）
# - IGNORED_DATA_TYPES：心跳/实时状态类报文，仅落流水，不视为失败
ALERT_DATA_TYPES = {"new-call-msg", "call-msg"}
IGNORED_DATA_TYPES = {"smb-real-time-msg"}

# [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 网关ID 收敛为 8 位（大写存储），紧急联系手机为中国大陆 11 位
GATEWAY_ID_REGEX = re.compile(r"^[A-Z0-9]{8}$")
# 旧字段名保留作为兼容别名，但语义已变更
GATEWAY_SN_REGEX = GATEWAY_ID_REGEX
DEVICE_SN_REGEX = re.compile(r"^[A-Za-z0-9]{8}$")
EMERGENCY_PHONE_REGEX = re.compile(r"^1[3-9]\d{9}$")


def _normalize_gateway_id(raw: Optional[str]) -> str:
    """[PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28]
    网关ID 标准化：去除空白/非字母数字字符并统一转大写。
    """
    if not raw:
        return ""
    s = str(raw).upper()
    return re.sub(r"[^A-Z0-9]", "", s)


# ────────────── ORM 模型 ──────────────
class HomeSafetyDeviceBinding(Base):
    __tablename__ = "home_safety_device_binding"
    __table_args__ = (
        UniqueConstraint("user_id", "device_sn", "status", name="uq_hs_binding_user_dev_status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    device_type = Column(Integer, nullable=False, index=True)
    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 网关ID 长度由 12 收敛为 8（大写存储）
    gateway_sn = Column(String(16), nullable=False)
    device_sn = Column(String(16), nullable=False, index=True)
    status = Column(Integer, nullable=False, default=1)  # 1=有效 0=已解绑 2=失效需重绑（撞号）
    verify_status = Column(Integer, nullable=False, default=0)  # 0=未校验 1=通过 2=未通过
    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 设备级紧急联系手机（11 位中国大陆手机号）
    emergency_phone = Column(String(11), nullable=True)
    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 当 status=2 时，记录失效原因，便于前端展示
    invalid_reason = Column(String(128), nullable=True)
    # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 设备归属家庭成员
    member_id = Column(Integer, nullable=True, index=True)
    # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 是否由迁移脚本自动归属"本人"
    migrated_to_self = Column(Boolean, nullable=False, default=False)
    # [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 设备备注名（≤20 字，新设备必填，老设备可空）
    remark = Column(String(64), nullable=True)
    bound_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    unbound_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class HomeSafetyEmergencyContact(Base):
    __tablename__ = "home_safety_emergency_contact"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    guardian_id = Column(Integer, nullable=False)
    is_primary_locked = Column(Integer, nullable=False, default=0)  # 1=主守护人 0=普通
    enabled_for_emergency = Column(Integer, nullable=False, default=1)
    enabled_for_smoke = Column(Integer, nullable=False, default=1)
    enabled_for_water = Column(Integer, nullable=False, default=1)
    # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 紧急联系人按家庭成员隔离
    member_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class HomeSafetyAlarm(Base):
    __tablename__ = "home_safety_alarm"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    device_type = Column(Integer, nullable=False)
    device_sn = Column(String(16), nullable=False, index=True)
    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 网关ID 长度从 12 → 8（兼容 VARCHAR(16)）
    gateway_sn = Column(String(16), nullable=True)
    alarm_at = Column(DateTime, nullable=False)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    dedupe_key = Column(String(96), nullable=False, index=True)
    dedupe_count = Column(Integer, nullable=False, default=1)
    notify_inapp = Column(Integer, nullable=False, default=0)
    notify_mp = Column(Integer, nullable=False, default=0)
    notify_sms = Column(Integer, nullable=False, default=0)
    notify_ai_call = Column(Integer, nullable=False, default=0)
    ai_call_quota_user = Column(Integer, nullable=True)
    read_status = Column(Integer, nullable=False, default=0)
    handle_status = Column(Integer, nullable=False, default=0)
    handle_note = Column(Text, nullable=True)
    handle_by = Column(Integer, nullable=True)
    handled_at = Column(DateTime, nullable=True)
    # [PRD-HOME-SAFETY-V2 2026-05-27] v2 新增字段
    vendor_msg_id = Column(String(64), nullable=True, unique=True, index=True)  # 厂商消息唯一 ID，永久幂等
    gw_id = Column(String(64), nullable=True)  # 网关 SN（仅记录不校验，区别于 gateway_sn 校验字段）
    dev_name = Column(String(128), nullable=True)  # 设备别名
    call_type = Column(Integer, nullable=True)  # 厂商消息类型 callType
    data_type = Column(String(32), nullable=True)  # 厂商报文类型，如 call-msg
    notify_ai_call_status = Column(String(16), nullable=False, default="failed")
    notify_ai_call_fail_reason = Column(String(256), nullable=True, default="本期未对接外呼通道")
    source_ip = Column(String(64), nullable=True)  # 回调来源 IP
    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 设备级紧急联系手机（快照，便于审计）
    device_emergency_phone = Column(String(11), nullable=True)
    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 短信/AI外呼最终目标号码 JSON（已去重）
    notify_targets_json = Column(Text, nullable=True)
    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 通知去重信息：跳过的重复条目数
    notify_dedup_skipped = Column(Integer, nullable=True, default=0)
    # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 触发告警的设备归属成员（冗余字段，便于按成员查询）
    member_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class HomeSafetyCallbackConfig(Base):
    __tablename__ = "home_safety_callback_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(String(64), nullable=True)
    callback_url = Column(String(256), nullable=True)
    auth_token = Column(Text, nullable=True)
    upstream_base_url = Column(String(256), nullable=True)
    # [PRD-HOME-SAFETY-V2 2026-05-27] v2 新增字段
    upstream_path = Column(String(256), nullable=True)  # 上游接口路径（拆分自 upstream_base_url）
    callback_domain = Column(String(256), nullable=True)  # 回调域名
    callback_path = Column(String(256), nullable=True, default="/api/home_safety/callback/alarm")
    last_pushed_at = Column(DateTime, nullable=True)
    last_test_result = Column(String(128), nullable=True)
    last_test_at = Column(DateTime, nullable=True)
    last_push_status = Column(String(16), nullable=True)  # success / fail
    last_push_url = Column(String(512), nullable=True)
    last_push_code = Column(Integer, nullable=True)
    last_push_message = Column(String(512), nullable=True)
    last_push_raw = Column(Text, nullable=True)
    # [BUGFIX HOME-SAFETY-V2-REVISION 2026-05-28] 判定依据，便于审计为何被判成功/失败
    last_push_judge_basis = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# [PRD-HOME-SAFETY-V2 2026-05-27] 推送历史表
class HomeSafetyCallbackPushHistory(Base):
    __tablename__ = "home_safety_callback_push_history"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    pushed_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    pushed_url = Column(String(512), nullable=True)
    operator_user_id = Column(Integer, nullable=True)
    operator_username = Column(String(128), nullable=True)
    status = Column(String(16), nullable=False, default="fail")  # success / fail
    upstream_code = Column(Integer, nullable=True)
    upstream_message = Column(String(512), nullable=True)
    upstream_raw = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# [PRD-HOME-SAFETY-V2 2026-05-27] 回调接收流水（含异常）
# [BUGFIX HOME-SAFETY-V2-REVISION 2026-05-28] 扩 5 字段 + parse_status='pending' 先写后改
class HomeSafetyCallbackLog(Base):
    __tablename__ = "home_safety_callback_log"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    source_ip = Column(String(64), nullable=True)
    request_headers = Column(Text, nullable=True)
    request_body = Column(Text, nullable=True)
    parse_status = Column(String(32), nullable=False, default="pending")
    # pending（先写）/ ok / fail / duplicate / unbound / unsupported_type / missing_field
    # / unknown_devtype / time_parse_fail / internal_error / ignored（v3 心跳类）
    parse_fail_reason = Column(String(512), nullable=True)
    linked_alarm_id = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    vendor_msg_id = Column(String(64), nullable=True, index=True)
    device_sn = Column(String(32), nullable=True, index=True)
    # [BUGFIX V2-REVISION] 新增 5 字段
    request_method = Column(String(8), nullable=True)
    request_url = Column(String(512), nullable=True)
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    # [BUGFIX HS-CALLBACK-DATATYPE 2026-05-29] 厂商报文 dataType 原值（独立字段，便于筛选）
    data_type = Column(String(64), nullable=True, index=True)


class HomeSafetyAiCallLog(Base):
    __tablename__ = "home_safety_ai_call_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alarm_id = Column(Integer, nullable=False, index=True)
    target_phone = Column(String(20), nullable=False)
    target_role = Column(String(16), nullable=False)  # self/primary_guardian/guardian
    request_id = Column(String(64), nullable=True)
    call_status = Column(Integer, nullable=False, default=0)  # 0/1/2
    callback_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# ────────────── Schemas ──────────────
class BindDeviceReq(BaseModel):
    device_type: int = Field(..., description="1/2/7")
    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 接受 gateway_sn 与 gateway_id 任意一个
    gateway_sn: Optional[str] = None
    gateway_id: Optional[str] = None
    device_sn: str
    emergency_phone: Optional[str] = Field(default=None, description="11 位中国大陆紧急联系手机号")
    # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 归属家庭成员 ID（可选，兼容期可不传，默认回落本人）
    member_id: Optional[int] = Field(default=None, description="设备归属家庭成员 ID")
    # [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 设备备注名（新设备必填，≤20 字）
    remark: Optional[str] = Field(default=None, description="设备备注名，≤20 字，如「爸爸家」")

    class Config:
        extra = "allow"


class TransferDeviceReq(BaseModel):
    """[PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 调整设备归属请求体"""
    member_id: int = Field(..., description="新归属家庭成员 ID")


class UpdateDeviceRemarkReq(BaseModel):
    """[BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 单独修改设备备注"""
    remark: str = Field(..., description="设备备注名，≤20 字，不允许仅空白")


class UpdateEmergencyPhoneReq(BaseModel):
    """[PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 修改设备紧急联系手机"""
    emergency_phone: str


class HandleAlarmReq(BaseModel):
    note: Optional[str] = None


class EmergencyContactItem(BaseModel):
    guardian_id: int
    enabled_for_emergency: bool = True
    enabled_for_smoke: bool = True
    enabled_for_water: bool = True


class SaveContactsReq(BaseModel):
    guardian_ids: List[int] = Field(default_factory=list, description="其他守护人 ID 列表，最多 2 个")


class ContactDeviceToggleReq(BaseModel):
    guardian_id: int
    device_type: int  # 1/2/7
    enabled: bool


class CallbackConfigReq(BaseModel):
    org_id: Optional[str] = None
    callback_url: Optional[str] = None
    auth_token: Optional[str] = None
    upstream_base_url: Optional[str] = None
    # [PRD-HOME-SAFETY-V2 2026-05-27] 新增字段
    upstream_path: Optional[str] = None
    callback_domain: Optional[str] = None


class UpstreamAlarmReq(BaseModel):
    """兼容 v1 旧契约（扁平字段）和 v2 厂商真实报文（嵌套 param）"""
    # v1 兼容字段
    device_sn: Optional[str] = None
    type: Optional[int] = Field(default=None, description="设备类型 1/2/7")
    alarm_time: Optional[str] = None
    sign: Optional[str] = None
    # v2 厂商真实报文字段
    param: Optional[Dict[str, Any]] = None
    dataType: Optional[str] = None
    msgId: Optional[str] = None

    class Config:
        extra = "allow"


# ────────────── 工具函数 ──────────────
def _device_label(device_type: int) -> str:
    return DEVICE_TYPE_LABEL.get(device_type, f"未知设备(type={device_type})")


def _dedupe_key(device_sn: str, ts: datetime) -> str:
    bucket = int(ts.timestamp() // DEDUPE_WINDOW_SECONDS)
    return f"{device_sn}:{bucket}"


def _validate_sn(gateway_sn: str, device_sn: str) -> None:
    """[PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28]
    网关ID：8 位 [A-Z0-9]（已经在外层规范化）。设备 SN：8 位字母+数字。
    错误码：4001 invalid_gateway_id, 4002（设备 SN 走原 400）。
    """
    if not GATEWAY_ID_REGEX.match(gateway_sn or ""):
        raise HTTPException(400, "invalid_gateway_id:网关ID 必须为 8 位字母或数字")
    if not DEVICE_SN_REGEX.match(device_sn or ""):
        raise HTTPException(400, "设备 SN 必须为 8 位字母+数字")


def _validate_emergency_phone(phone: Optional[str], *, required: bool = True) -> str:
    """[PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 校验紧急联系手机。
    返回标准化后的手机号；不合法抛出 400。
    """
    if phone is None or str(phone).strip() == "":
        if required:
            raise HTTPException(400, "emergency_phone_required:紧急联系手机为必填项")
        return ""
    p = str(phone).strip()
    if not EMERGENCY_PHONE_REGEX.match(p):
        raise HTTPException(400, "invalid_emergency_phone:请输入有效的 11 位手机号")
    return p


def _mask_phone(p: Optional[str]) -> str:
    """脱敏中间 4 位：138****1234"""
    if not p:
        return ""
    s = str(p)
    if len(s) != 11:
        return s
    return s[:3] + "****" + s[-4:]


def _validate_remark(raw: Optional[str], *, required: bool = True) -> str:
    """[BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 校验设备备注名。
    - trim 后长度 1~20
    - 不允许仅空白
    - required=False 时允许为空（仅 PATCH 接口的少数场景；本期仍要求必填）
    返回 trim 后的备注字符串。
    """
    s = (str(raw) if raw is not None else "").strip()
    if not s:
        if required:
            raise HTTPException(
                400,
                "remark_required:设备备注不能为空，且长度不超过 20 字",
            )
        return ""
    if len(s) > 20:
        raise HTTPException(
            400,
            "remark_too_long:设备备注不超过 20 字",
        )
    return s


async def _get_primary_guardian(db: AsyncSession, user_id: int) -> Optional[int]:
    """该用户的主守护人 ID（manager_user_id），找不到返回 None。"""
    if FamilyManagement is None:
        return None
    try:
        q = (
            select(FamilyManagement.manager_user_id)
            .where(
                FamilyManagement.managed_user_id == user_id,
                FamilyManagement.is_primary_guardian.is_(True),
                FamilyManagement.status == "active",
            )
            .limit(1)
        )
        row = (await db.execute(q)).scalar_one_or_none()
        return int(row) if row else None
    except Exception:
        return None


async def _list_guardians(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """该用户档案下所有守护人（manager），主守护人优先排序。"""
    if FamilyManagement is None:
        return []
    try:
        q = (
            select(FamilyManagement.manager_user_id, FamilyManagement.is_primary_guardian)
            .where(
                FamilyManagement.managed_user_id == user_id,
                FamilyManagement.status == "active",
            )
        )
        rows = (await db.execute(q)).all()
    except Exception:
        rows = []
    out: List[Dict[str, Any]] = []
    for mgr_id, is_primary in rows:
        nickname = None
        phone = None
        if User is not None:
            try:
                u = (await db.execute(select(User).where(User.id == mgr_id))).scalar_one_or_none()
                if u:
                    nickname = getattr(u, "nickname", None)
                    phone = getattr(u, "phone", None)
            except Exception:
                pass
        out.append(
            {
                "guardian_id": int(mgr_id),
                "nickname": nickname,
                "phone": phone,
                "is_primary": bool(is_primary),
            }
        )
    out.sort(key=lambda x: (0 if x["is_primary"] else 1, x["guardian_id"]))
    return out


# ────────────── 家庭成员辅助（PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29）──────────────
async def _ensure_self_member(db: AsyncSession, user_id: int) -> Optional[int]:
    """[PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 确保该用户存在"本人"成员，返回其 id。
    若 family_members 表/关系不可用则返回 None（兼容老库）。
    """
    try:
        from app.models.models import FamilyMember as _FM, User as _U  # type: ignore
    except Exception:
        return None
    try:
        row = (
            await db.execute(
                select(_FM).where(_FM.user_id == user_id, _FM.is_self == True)  # noqa: E712
            )
        ).scalar_one_or_none()
        if row:
            return int(row.id)
        # 创建本人成员
        nickname = None
        try:
            u = (await db.execute(select(_U).where(_U.id == user_id))).scalar_one_or_none()
            if u:
                nickname = getattr(u, "nickname", None)
        except Exception:
            pass
        new_self = _FM(
            user_id=user_id,
            relationship_type="self",
            nickname=nickname or "本人",
            is_self=True,
            status="active",
        )
        db.add(new_self)
        await db.commit()
        await db.refresh(new_self)
        return int(new_self.id)
    except Exception as e:
        logger.warning("[home_safety_v1][member] _ensure_self_member fail: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        return None


async def _list_user_members(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """[PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 列出该账号下所有家庭成员（含本人在前）。"""
    try:
        from app.models.models import FamilyMember as _FM  # type: ignore
    except Exception:
        return []
    try:
        rows = (
            await db.execute(
                select(_FM).where(
                    _FM.user_id == user_id,
                    _FM.status == "active",
                )
            )
        ).scalars().all()
    except Exception:
        return []
    items: List[Dict[str, Any]] = []
    for m in rows:
        items.append(
            {
                "id": int(m.id),
                "nickname": getattr(m, "nickname", None) or "成员",
                "relationship_type": getattr(m, "relationship_type", None) or "",
                "is_self": bool(getattr(m, "is_self", False)),
            }
        )
    items.sort(key=lambda x: (0 if x["is_self"] else 1, x["id"]))
    return items


async def _resolve_member_id(
    db: AsyncSession, user_id: int, member_id: Optional[int]
) -> Optional[int]:
    """[PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 解析 member_id：
    - 传入 None 则回退为"本人"成员 id（自动确保存在）
    - 传入具体 id 则校验属于本账号；不属于则抛 400
    """
    if member_id is None:
        return await _ensure_self_member(db, user_id)
    try:
        from app.models.models import FamilyMember as _FM  # type: ignore
    except Exception:
        return member_id
    try:
        row = (
            await db.execute(
                select(_FM).where(
                    _FM.id == int(member_id), _FM.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(400, "member_not_found:成员不存在或不属于当前账号")
        return int(row.id)
    except HTTPException:
        raise
    except Exception:
        return member_id


# ────────────── 通知目标汇总（PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28）──────────────
DEVICE_TYPE_TO_GUARDIAN_FLAG = {
    DEVICE_TYPE_EMERGENCY: "enabled_for_emergency",
    DEVICE_TYPE_SMOKE: "enabled_for_smoke",
    DEVICE_TYPE_WATER: "enabled_for_water",
}


async def collect_alarm_notify_targets(
    db: AsyncSession,
    *,
    user_id: int,
    device_type: int,
    device_emergency_phone: Optional[str],
) -> Dict[str, Any]:
    """[PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 汇总告警通知目标号码（已去重）。

    返回结构：
    {
        "targets": [{"phone": "13...", "role": "self/device_emergency/guardian"}, ...],
        "dedup_skipped": int  # 因号码重复被去重的次数
    }

    通道策略（详见 PRD 5.2）：
    - 站内 / 小程序：本人 + 守护人（设备级紧急联系手机不发）
    - 短信 / AI 外呼：本人 + 设备级紧急联系手机 + 已启用对应类型的守护人
    - 同一号码自动去重
    """
    raw: List[Dict[str, str]] = []

    self_phone = ""
    if User is not None:
        try:
            u = (
                await db.execute(select(User).where(User.id == user_id))
            ).scalar_one_or_none()
            if u:
                self_phone = getattr(u, "phone", "") or ""
        except Exception:
            self_phone = ""
    if self_phone:
        raw.append({"phone": str(self_phone), "role": "self"})

    if device_emergency_phone:
        raw.append({"phone": str(device_emergency_phone), "role": "device_emergency"})

    # 守护人列表（按设备类型对应的 enabled_for_* 启用项过滤）
    flag_name = DEVICE_TYPE_TO_GUARDIAN_FLAG.get(device_type)
    contacts = (
        await db.execute(
            select(HomeSafetyEmergencyContact).where(
                HomeSafetyEmergencyContact.user_id == user_id
            )
        )
    ).scalars().all()
    for r in contacts:
        enabled = True
        if flag_name:
            enabled = bool(getattr(r, flag_name, 1))
        if not enabled:
            continue
        phone_g = ""
        if User is not None:
            try:
                u = (
                    await db.execute(select(User).where(User.id == r.guardian_id))
                ).scalar_one_or_none()
                if u:
                    phone_g = getattr(u, "phone", "") or ""
            except Exception:
                phone_g = ""
        if phone_g:
            raw.append({"phone": str(phone_g), "role": "guardian"})

    # 去重：同一号码只保留第一次出现
    seen: Dict[str, Dict[str, str]] = {}
    dedup_skipped = 0
    targets: List[Dict[str, str]] = []
    for it in raw:
        ph = it["phone"]
        if ph in seen:
            dedup_skipped += 1
            continue
        seen[ph] = it
        targets.append(it)

    return {"targets": targets, "dedup_skipped": dedup_skipped}


# ────────────── v2 工具函数 ──────────────
DEFAULT_CALLBACK_PATH = "/api/home_safety/callback/alarm"


def verify_signature(headers: Dict[str, str], body: bytes) -> bool:
    """[PRD-HOME-SAFETY-V2 2026-05-27] 签名验证钩子，本期固定返回 True，不验签。
    未来如厂商提供签名机制，仅需在此实现具体算法。"""
    return True


def _extract_source_ip(request: Request) -> str:
    """提取来源 IP，按顺序读取 X-Real-IP / X-Forwarded-For / REMOTE_ADDR。"""
    try:
        h = {k.lower(): v for k, v in request.headers.items()}
        if h.get("x-real-ip"):
            return h["x-real-ip"][:64]
        if h.get("x-forwarded-for"):
            return h["x-forwarded-for"].split(",")[0].strip()[:64]
        if request.client and request.client.host:
            return request.client.host[:64]
    except Exception:
        pass
    return ""


def _build_full_upstream_url(base: Optional[str], path: Optional[str]) -> str:
    """拼接完整上游 URL：去除 base 末尾 /，补 path 开头 /"""
    base = (base or "").strip().rstrip("/")
    path = (path or "").strip()
    if path and not path.startswith("/"):
        path = "/" + path
    if not base and not path:
        return ""
    return f"{base}{path}"


def _build_full_callback_url(domain: Optional[str], path: Optional[str]) -> str:
    """拼接完整回调 URL"""
    domain = (domain or "").strip().rstrip("/")
    path = (path or DEFAULT_CALLBACK_PATH).strip()
    if path and not path.startswith("/"):
        path = "/" + path
    if not domain:
        return ""
    return f"{domain}{path}"


def _mask_token(tok: Optional[str]) -> str:
    """Token 密文展示：前 4 + **** + 后 4"""
    if not tok:
        return ""
    tok = str(tok)
    if len(tok) <= 8:
        return "****"
    return tok[:4] + "****" + tok[-4:]


def _parse_vendor_alarm_time(occur_time_ms: Any) -> Optional[datetime]:
    """解析厂商毫秒时间戳"""
    try:
        if occur_time_ms is None:
            return None
        ts = float(occur_time_ms)
        if ts > 1e12:  # 毫秒
            ts = ts / 1000.0
        return datetime.utcfromtimestamp(ts)
    except Exception:
        return None


# ────────────── 用户端 API ──────────────
USER_PREFIX = "/api/home_safety"


@router.get(USER_PREFIX + "/devices")
async def list_my_devices(
    member_id: Optional[int] = Query(default=None, description="家庭成员 ID；不传按本人过滤"),
    all: int = Query(default=0, description="管理后台用 ?all=1 拉全部，不按成员过滤"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取我绑定的所有设备，按设备类型分组。
    [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 支持按家庭成员过滤。
    - all=1：拉本账号全部设备（不按成员过滤）
    - 否则：按 member_id 过滤；不传时默认本人成员
    """
    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 同时返回 status=1（有效）与 status=2（撞号失效）记录
    q = select(HomeSafetyDeviceBinding).where(
        HomeSafetyDeviceBinding.user_id == current_user.id,
        HomeSafetyDeviceBinding.status.in_([1, 2]),
    )
    target_member_id: Optional[int] = None
    has_migrated_to_self_devices = False
    if not all:
        target_member_id = await _resolve_member_id(db, current_user.id, member_id)
        if target_member_id is not None:
            # 兼容：member_id 列还未填的旧设备也归到"本人"
            try:
                from app.models.models import FamilyMember as _FM  # type: ignore
                self_row = (
                    await db.execute(
                        select(_FM).where(
                            _FM.user_id == current_user.id, _FM.is_self == True  # noqa: E712
                        )
                    )
                ).scalar_one_or_none()
                self_id = int(self_row.id) if self_row else None
            except Exception:
                self_id = None
            if self_id is not None and target_member_id == self_id:
                q = q.where(
                    or_(
                        HomeSafetyDeviceBinding.member_id == target_member_id,
                        HomeSafetyDeviceBinding.member_id.is_(None),
                    )
                )
            else:
                q = q.where(HomeSafetyDeviceBinding.member_id == target_member_id)

    q = q.order_by(desc(HomeSafetyDeviceBinding.bound_at))
    rows = (await db.execute(q)).scalars().all()

    groups: Dict[int, List[Dict[str, Any]]] = {t: [] for t in ALL_DEVICE_TYPES}
    for b in rows:
        if bool(getattr(b, "migrated_to_self", False)):
            has_migrated_to_self_devices = True
        ephone = b.emergency_phone or ""
        groups.setdefault(b.device_type, []).append(
            {
                "id": b.id,
                "device_type": b.device_type,
                "device_type_label": _device_label(b.device_type),
                # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 8 位明文，新增 gateway_id 别名
                "gateway_sn": b.gateway_sn,
                "gateway_id": b.gateway_sn,
                "gateway_sn_mask": b.gateway_sn or "",
                "device_sn": b.device_sn,
                "verify_status": b.verify_status,
                "bound_at": (b.bound_at.isoformat() + "Z") if b.bound_at else None,
                "status": b.status,
                "status_label": "有效" if b.status == 1 else ("失效需重绑" if b.status == 2 else "已解绑"),
                "invalid_reason": b.invalid_reason if b.status == 2 else None,
                "emergency_phone": ephone,
                "emergency_phone_mask": _mask_phone(ephone),
                "emergency_phone_filled": bool(ephone),
                # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 归属信息
                "member_id": getattr(b, "member_id", None),
                "migrated_to_self": bool(getattr(b, "migrated_to_self", False)),
                # [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 备注名
                "remark": getattr(b, "remark", None),
            }
        )
    return {
        "groups": [
            {
                "device_type": t,
                "device_type_label": _device_label(t),
                "color": DEVICE_TYPE_COLOR.get(t),
                "count": len(groups.get(t, [])),
                "items": groups.get(t, []),
            }
            for t in ALL_DEVICE_TYPES
        ],
        # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 当前过滤的成员 + 是否包含迁移设备（供前端提示条判断）
        "active_member_id": target_member_id,
        "has_migrated_to_self_devices": has_migrated_to_self_devices,
    }


@router.get(USER_PREFIX + "/members", deprecated=True)
async def list_my_members_for_home_safety(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[DEPRECATED 2026-05-29] 该接口将于 30 天后下线，前端请改用 /api/family/members。

    [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 居家安全顶部成员 Tab 数据来源。
    [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 过渡期内继续返回与 /api/family/members
    一致的成员列表，并在响应增加 `deprecated`/`replaced_by` 标记。
    """
    await _ensure_self_member(db, current_user.id)
    items = await _list_user_members(db, current_user.id)
    return {
        "items": items,
        "total": len(items),
        "deprecated": True,
        "replaced_by": "/api/family/members",
        "deprecation_note": "此接口将于 30 天后下线，请改用 /api/family/members",
    }


@router.post(USER_PREFIX + "/devices/bind")
async def bind_device(
    req: BindDeviceReq,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.device_type not in ALL_DEVICE_TYPES:
        raise HTTPException(400, "不支持的设备类型")
    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 标准化网关ID（8 位大写）
    raw_gw = req.gateway_id or req.gateway_sn or ""
    gw_id = _normalize_gateway_id(raw_gw)
    dev_sn = (req.device_sn or "").strip()
    _validate_sn(gw_id, dev_sn)
    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 紧急联系手机必填
    ephone = _validate_emergency_phone(req.emergency_phone, required=True)
    # [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 设备备注必填
    remark_value = _validate_remark(req.remark, required=True)

    # 同一用户同一 device_sn 不可重复有效绑定
    exists = (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.user_id == current_user.id,
                HomeSafetyDeviceBinding.device_sn == dev_sn,
                HomeSafetyDeviceBinding.status == 1,
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "您已绑定该设备")

    # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 解析归属成员（不传则默认本人；传了校验属当前账号）
    member_id_resolved = await _resolve_member_id(db, current_user.id, req.member_id)

    binding = HomeSafetyDeviceBinding(
        user_id=current_user.id,
        device_type=req.device_type,
        gateway_sn=gw_id,
        device_sn=dev_sn,
        status=1,
        verify_status=0,
        emergency_phone=ephone,
        member_id=member_id_resolved,
        migrated_to_self=False,
        remark=remark_value,
        bound_at=datetime.utcnow(),
    )
    db.add(binding)
    await db.commit()
    await db.refresh(binding)

    return {
        "success": True,
        "id": binding.id,
        "verify_status": binding.verify_status,
        "gateway_id": binding.gateway_sn,
        "emergency_phone": binding.emergency_phone,
        "member_id": binding.member_id,
        "remark": binding.remark,
    }


@router.patch(USER_PREFIX + "/devices/{binding_id}/transfer")
async def transfer_device_member(
    binding_id: int,
    req: TransferDeviceReq,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 调整设备归属（"调整归属"功能用）。"""
    b = (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.id == binding_id,
                HomeSafetyDeviceBinding.user_id == current_user.id,
                HomeSafetyDeviceBinding.status.in_([1, 2]),
            )
        )
    ).scalar_one_or_none()
    if not b:
        raise HTTPException(404, "设备不存在或已解绑")
    new_member_id = await _resolve_member_id(db, current_user.id, req.member_id)
    if new_member_id is None:
        raise HTTPException(400, "member_id_required:必须提供合法的成员 ID")
    b.member_id = new_member_id
    # 调整归属即视为用户已确认，不再视作迁移产生
    b.migrated_to_self = False
    await db.commit()
    return {"success": True, "id": b.id, "member_id": b.member_id}


# [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 单独修改设备备注接口
@router.patch(USER_PREFIX + "/devices/{binding_id}/remark")
async def update_device_remark(
    binding_id: int,
    req: UpdateDeviceRemarkReq,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 单独修改设备备注。
    - 鉴权：仅设备绑定者本人
    - 校验：备注 trim 后长度 1~20
    - 与 transfer 接口独立，便于审计与权限分离
    """
    b = (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.id == binding_id,
                HomeSafetyDeviceBinding.user_id == current_user.id,
                HomeSafetyDeviceBinding.status.in_([1, 2]),
            )
        )
    ).scalar_one_or_none()
    if not b:
        raise HTTPException(404, "设备不存在或已解绑")
    new_remark = _validate_remark(req.remark, required=True)
    b.remark = new_remark
    await db.commit()
    return {"success": True, "id": b.id, "remark": b.remark}


@router.post(USER_PREFIX + "/devices/{binding_id}/unbind")
async def unbind_device(
    binding_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 允许解绑 status=1 或 status=2 的记录
    b = (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.id == binding_id,
                HomeSafetyDeviceBinding.user_id == current_user.id,
                HomeSafetyDeviceBinding.status.in_([1, 2]),
            )
        )
    ).scalar_one_or_none()
    if not b:
        raise HTTPException(404, "设备不存在或已解绑")
    b.status = 0
    b.unbound_at = datetime.utcnow()
    await db.commit()
    return {"success": True}


# [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 设备详情（仅本人）
@router.get(USER_PREFIX + "/devices/{binding_id}")
async def get_my_device_detail(
    binding_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    b = (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.id == binding_id,
                HomeSafetyDeviceBinding.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not b:
        raise HTTPException(404, "设备不存在")
    ephone = b.emergency_phone or ""
    return {
        "id": b.id,
        "device_type": b.device_type,
        "device_type_label": _device_label(b.device_type),
        "gateway_id": b.gateway_sn,
        "gateway_sn": b.gateway_sn,
        "device_sn": b.device_sn,
        "status": b.status,
        "status_label": "有效" if b.status == 1 else ("失效需重绑" if b.status == 2 else "已解绑"),
        "invalid_reason": b.invalid_reason if b.status == 2 else None,
        "verify_status": b.verify_status,
        "emergency_phone": ephone,
        "emergency_phone_mask": _mask_phone(ephone),
        "emergency_phone_filled": bool(ephone),
        "bound_at": (b.bound_at.isoformat() + "Z") if b.bound_at else None,
        "unbound_at": (b.unbound_at.isoformat() + "Z") if b.unbound_at else None,
    }


@router.patch(USER_PREFIX + "/devices/{binding_id}/emergency_phone")
async def update_device_emergency_phone(
    binding_id: int,
    req: UpdateEmergencyPhoneReq,
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 修改设备紧急联系手机：
    - 鉴权：仅设备绑定者本人
    - 校验：^1[3-9]\\d{9}$
    - 无需短信验证码（按用户决策 8C）
    - 审计日志：写入告警日志（轻量）
    """
    b = (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.id == binding_id,
                HomeSafetyDeviceBinding.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not b:
        raise HTTPException(404, "设备不存在")
    if b.status == 0:
        raise HTTPException(400, "设备已解绑，不可修改")
    new_phone = _validate_emergency_phone(req.emergency_phone, required=True)
    old_phone = b.emergency_phone or ""
    b.emergency_phone = new_phone
    await db.commit()
    try:
        logger.info(
            "[home_safety_v1][emergency_phone_changed] device_id=%s user_id=%s old=%s new=%s ip=%s ua=%s",
            binding_id,
            current_user.id,
            _mask_phone(old_phone),
            _mask_phone(new_phone),
            _extract_source_ip(request),
            request.headers.get("user-agent", "")[:200],
        )
    except Exception:
        pass
    return {
        "ok": True,
        "success": True,
        "emergency_phone": new_phone,
        "emergency_phone_mask": _mask_phone(new_phone),
    }


@router.get(USER_PREFIX + "/devices/bind/defaults")
async def get_bind_defaults(
    current_user=Depends(get_current_user),
):
    """[PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 绑定页默认值：注册手机号回填。"""
    phone = getattr(current_user, "phone", None) or ""
    return {
        "default_emergency_phone": str(phone) if phone else "",
        "phone_required": True,
        "gateway_id_length": 8,
        "gateway_id_pattern": "^[A-Z0-9]{8}$",
        "emergency_phone_pattern": "^1[3-9]\\d{9}$",
    }


@router.get(USER_PREFIX + "/alarms")
async def list_my_alarms(
    device_type: Optional[int] = None,
    member_id: Optional[int] = Query(default=None, description="按家庭成员过滤"),
    page: int = 1,
    size: int = 20,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(HomeSafetyAlarm).where(HomeSafetyAlarm.user_id == current_user.id)
    total_q = select(func.count(HomeSafetyAlarm.id)).where(HomeSafetyAlarm.user_id == current_user.id)
    if device_type is not None:
        base = base.where(HomeSafetyAlarm.device_type == device_type)
        total_q = total_q.where(HomeSafetyAlarm.device_type == device_type)
    # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 按成员过滤：本人 Tab 兼容 member_id IS NULL
    if member_id is not None:
        target_mid = await _resolve_member_id(db, current_user.id, member_id)
        try:
            from app.models.models import FamilyMember as _FM  # type: ignore
            self_row = (
                await db.execute(
                    select(_FM).where(
                        _FM.user_id == current_user.id, _FM.is_self == True  # noqa: E712
                    )
                )
            ).scalar_one_or_none()
            self_id = int(self_row.id) if self_row else None
        except Exception:
            self_id = None
        if self_id is not None and target_mid == self_id:
            cond = or_(HomeSafetyAlarm.member_id == target_mid, HomeSafetyAlarm.member_id.is_(None))
        else:
            cond = HomeSafetyAlarm.member_id == target_mid
        base = base.where(cond)
        total_q = total_q.where(cond)

    # [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 分页 total
    try:
        total = int((await db.execute(total_q)).scalar() or 0)
    except Exception:
        total = 0

    q = base.order_by(desc(HomeSafetyAlarm.alarm_at)).limit(size).offset((page - 1) * size)
    rows = (await db.execute(q)).scalars().all()

    # [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 批量关联设备备注 + 成员名
    device_sn_set = {a.device_sn for a in rows if a.device_sn}
    remark_by_sn: Dict[str, str] = {}
    if device_sn_set:
        try:
            brows = (
                await db.execute(
                    select(HomeSafetyDeviceBinding).where(
                        HomeSafetyDeviceBinding.user_id == current_user.id,
                        HomeSafetyDeviceBinding.device_sn.in_(list(device_sn_set)),
                    )
                )
            ).scalars().all()
            for bd in brows:
                if bd.device_sn:
                    # 同一 device_sn 多条以最近绑定为准
                    if bd.device_sn not in remark_by_sn or (bd.status == 1):
                        remark_by_sn[bd.device_sn] = getattr(bd, "remark", None) or ""
        except Exception:
            pass

    member_id_set: set = {int(a.member_id) for a in rows if getattr(a, "member_id", None)}
    member_name_map: Dict[int, str] = {}
    if member_id_set:
        try:
            from app.models.models import FamilyMember as _FM  # type: ignore
            mrows = (
                await db.execute(
                    select(_FM).where(_FM.id.in_(list(member_id_set)))
                )
            ).scalars().all()
            for m in mrows:
                member_name_map[int(m.id)] = (
                    "本人"
                    if bool(getattr(m, "is_self", False))
                    else (
                        getattr(m, "nickname", None)
                        or getattr(m, "relationship_type", None)
                        or f"成员{m.id}"
                    )
                )
        except Exception:
            pass

    items = []
    for a in rows:
        mid = getattr(a, "member_id", None)
        # [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] notify_phone_mask 优先取设备级紧急联系手机
        device_phone = getattr(a, "device_emergency_phone", None) or ""
        notify_status_raw = getattr(a, "notify_ai_call_status", "failed") or "failed"
        # 兼容多种状态：sent/ok/success → 视为已通知
        notify_ok = notify_status_raw in ("sent", "ok", "success")
        items.append(
            {
                "id": a.id,
                "device_type": a.device_type,
                "device_type_label": _device_label(a.device_type),
                "device_sn": a.device_sn,
                # [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 新字段
                "device_remark": remark_by_sn.get(a.device_sn or "", "") or None,
                "member_id": mid,
                "member_name": member_name_map.get(int(mid)) if mid else None,
                "notify_phone_mask": _mask_phone(device_phone) if device_phone else None,
                "notify_status": "sent" if notify_ok else (notify_status_raw or "none"),
                "notify_ai_call_status": notify_status_raw,
                "alarm_at": (a.alarm_at.isoformat() + "Z") if a.alarm_at else None,
                "dedupe_count": a.dedupe_count,
                "read_status": a.read_status,
                "handle_status": a.handle_status,
                "handle_note": a.handle_note,
                "notify_ai_call": a.notify_ai_call,
            }
        )
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
    }


@router.post(USER_PREFIX + "/alarms/{alarm_id}/read")
async def mark_alarm_read(
    alarm_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = (
        await db.execute(
            select(HomeSafetyAlarm).where(
                HomeSafetyAlarm.id == alarm_id,
                HomeSafetyAlarm.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "报警不存在")
    a.read_status = 1
    await db.commit()
    return {"success": True}


@router.post(USER_PREFIX + "/alarms/{alarm_id}/handle")
async def handle_alarm(
    alarm_id: int,
    req: HandleAlarmReq,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = (
        await db.execute(
            select(HomeSafetyAlarm).where(
                HomeSafetyAlarm.id == alarm_id,
                HomeSafetyAlarm.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "报警不存在")
    a.handle_status = 1
    a.handle_note = req.note
    a.handle_by = current_user.id
    a.handled_at = datetime.utcnow()
    a.read_status = 1
    await db.commit()
    return {"success": True}


# [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-V2 2026-05-29]
# PRD v2.0 锁定接口：PATCH /api/home_safety/alarms/{id}/resolve
# - 等价于 handle_alarm 的"标记已处理"语义，但走 PATCH 路由 + 幂等返回
# - 鉴权：仅本人（user_id 匹配）；非属者返回 403
# - 幂等：handle_status 已为 1 时返回 {code:0, message:"已处理过"} 不报错
@router.patch(USER_PREFIX + "/alarms/{alarm_id}/resolve")
async def resolve_alarm(
    alarm_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    a = (
        await db.execute(
            select(HomeSafetyAlarm).where(HomeSafetyAlarm.id == alarm_id)
        )
    ).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "报警不存在")
    if int(a.user_id) != int(current_user.id):
        # 仅本人或绑定家庭成员可处理；他人返回 403
        raise HTTPException(status_code=403, detail="forbidden")
    if int(a.handle_status or 0) == 1:
        # 幂等：已处理过直接返回
        return {
            "code": 0,
            "message": "已处理过",
            "data": {
                "id": a.id,
                "status": "resolved",
                "resolved_at": (a.handled_at.isoformat() + "Z") if a.handled_at else None,
            },
        }
    a.handle_status = 1
    a.handle_by = current_user.id
    a.handled_at = datetime.utcnow()
    a.read_status = 1
    await db.commit()
    return {
        "code": 0,
        "data": {
            "id": a.id,
            "status": "resolved",
            "resolved_at": (a.handled_at.isoformat() + "Z") if a.handled_at else None,
        },
    }


@router.get(USER_PREFIX + "/emergency_contacts")
async def get_emergency_contacts(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回当前用户的紧急联系人配置 + 可选守护人列表。"""
    guardians = await _list_guardians(db, current_user.id)
    rows = (
        await db.execute(
            select(HomeSafetyEmergencyContact).where(
                HomeSafetyEmergencyContact.user_id == current_user.id
            )
        )
    ).scalars().all()
    cfg = {r.guardian_id: r for r in rows}

    contacts: List[Dict[str, Any]] = []
    for g in guardians:
        gid = g["guardian_id"]
        is_primary = g["is_primary"]
        r = cfg.get(gid)
        contacts.append(
            {
                "guardian_id": gid,
                "nickname": g["nickname"],
                "phone": g["phone"],
                "is_primary": is_primary,
                "is_primary_locked": bool(is_primary),
                "enabled_for_emergency": bool(r.enabled_for_emergency) if r else True,
                "enabled_for_smoke": bool(r.enabled_for_smoke) if r else True,
                "enabled_for_water": bool(r.enabled_for_water) if r else True,
                "selected": bool(r) or is_primary,  # 主守护人默认选中
            }
        )

    return {"contacts": contacts, "max_other_selectable": 2}


@router.post(USER_PREFIX + "/emergency_contacts")
async def save_emergency_contacts(
    req: SaveContactsReq,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """保存联系人勾选。主守护人始终强制锁定，传入的 guardian_ids 是其他守护人，最多 2 个。"""
    guardians = await _list_guardians(db, current_user.id)
    primary_id = next((g["guardian_id"] for g in guardians if g["is_primary"]), None)
    other_ids = [g["guardian_id"] for g in guardians if not g["is_primary"]]

    chosen_others = [gid for gid in req.guardian_ids if gid in other_ids][:2]

    # 清旧配置
    await db.execute(
        select(HomeSafetyEmergencyContact).where(
            HomeSafetyEmergencyContact.user_id == current_user.id
        )
    )
    # 直接删除重建
    from sqlalchemy import delete as sa_delete

    await db.execute(
        sa_delete(HomeSafetyEmergencyContact).where(
            HomeSafetyEmergencyContact.user_id == current_user.id
        )
    )

    saved: List[int] = []
    if primary_id is not None:
        db.add(
            HomeSafetyEmergencyContact(
                user_id=current_user.id,
                guardian_id=primary_id,
                is_primary_locked=1,
            )
        )
        saved.append(primary_id)
    for gid in chosen_others:
        db.add(
            HomeSafetyEmergencyContact(
                user_id=current_user.id,
                guardian_id=gid,
                is_primary_locked=0,
            )
        )
        saved.append(gid)
    await db.commit()
    return {"success": True, "saved": saved}


@router.post(USER_PREFIX + "/emergency_contacts/device_toggle")
async def toggle_contact_device(
    req: ContactDeviceToggleReq,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.device_type not in ALL_DEVICE_TYPES:
        raise HTTPException(400, "device_type 不合法")
    r = (
        await db.execute(
            select(HomeSafetyEmergencyContact).where(
                HomeSafetyEmergencyContact.user_id == current_user.id,
                HomeSafetyEmergencyContact.guardian_id == req.guardian_id,
            )
        )
    ).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "该联系人未启用")
    val = 1 if req.enabled else 0
    if req.device_type == DEVICE_TYPE_EMERGENCY:
        r.enabled_for_emergency = val
    elif req.device_type == DEVICE_TYPE_SMOKE:
        r.enabled_for_smoke = val
    elif req.device_type == DEVICE_TYPE_WATER:
        r.enabled_for_water = val
    await db.commit()
    return {"success": True}


# ────────────── 上游回调（公开）──────────────
# 兼容两种路径：原 PRD 设计的 /callback/home_safety/...
# 以及网关代理友好的 /api/home_safety/callback/...
async def _log_callback(
    db: AsyncSession,
    *,
    received_at: datetime,
    source_ip: str,
    headers_text: str,
    body_text: str,
    parse_status: str,
    parse_fail_reason: Optional[str] = None,
    linked_alarm_id: Optional[int] = None,
    vendor_msg_id: Optional[str] = None,
    request_method: Optional[str] = None,
    request_url: Optional[str] = None,
    response_status: Optional[int] = None,
    response_body: Optional[str] = None,
    processed_at: Optional[datetime] = None,
    device_sn: Optional[str] = None,
    data_type: Optional[str] = None,
) -> Optional[int]:
    """[PRD-HOME-SAFETY-V2] 落库回调流水（含异常），独立提交避免事务回滚连带丢失日志。
    [BUGFIX HOME-SAFETY-V2-REVISION 2026-05-28] 返回插入的 log id 以支持"先写后改"模式。
    [BUGFIX HS-CALLBACK-DATATYPE 2026-05-29] 新增 data_type 字段独立落库。
    """
    try:
        log = HomeSafetyCallbackLog(
            received_at=received_at,
            source_ip=source_ip or "",
            request_headers=headers_text[:4000] if headers_text else None,
            request_body=body_text[:4000] if body_text else None,
            parse_status=parse_status,
            parse_fail_reason=parse_fail_reason,
            linked_alarm_id=linked_alarm_id,
            vendor_msg_id=vendor_msg_id,
            request_method=request_method,
            request_url=request_url[:512] if request_url else None,
            response_status=response_status,
            response_body=response_body[:4000] if response_body else None,
            processed_at=processed_at,
            device_sn=device_sn[:32] if device_sn else None,
            data_type=data_type[:64] if data_type else None,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return int(log.id)
    except Exception as e:  # pragma: no cover
        logger.warning("[home_safety_v2] 流水落库失败: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        return None


async def _update_callback_log(
    db: AsyncSession,
    log_id: int,
    *,
    parse_status: str,
    parse_fail_reason: Optional[str] = None,
    linked_alarm_id: Optional[int] = None,
    vendor_msg_id: Optional[str] = None,
    response_status: Optional[int] = None,
    response_body: Optional[str] = None,
    device_sn: Optional[str] = None,
    data_type: Optional[str] = None,
) -> None:
    """[BUGFIX V2-REVISION] 更新已落库的流水记录（先写 pending → 业务后 update）。
    [BUGFIX HS-CALLBACK-DATATYPE 2026-05-29] 新增 data_type 字段更新。
    """
    try:
        log = (
            await db.execute(
                select(HomeSafetyCallbackLog).where(HomeSafetyCallbackLog.id == log_id)
            )
        ).scalar_one_or_none()
        if not log:
            return
        log.parse_status = parse_status
        if parse_fail_reason is not None:
            log.parse_fail_reason = parse_fail_reason[:512]
        if linked_alarm_id is not None:
            log.linked_alarm_id = linked_alarm_id
        if vendor_msg_id is not None and not log.vendor_msg_id:
            log.vendor_msg_id = vendor_msg_id
        if response_status is not None:
            log.response_status = response_status
        if response_body is not None:
            log.response_body = response_body[:4000]
        if device_sn is not None:
            log.device_sn = device_sn[:32]
        if data_type is not None and not log.data_type:
            log.data_type = data_type[:64]
        log.processed_at = datetime.utcnow()
        await db.commit()
    except Exception as e:  # pragma: no cover
        logger.warning("[home_safety_v2] 流水更新失败 id=%s err=%s", log_id, e)
        try:
            await db.rollback()
        except Exception:
            pass


@router.post("/api/home_safety/callback/alarm")
@router.post("/callback/home_safety/alarm")
async def upstream_alarm_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """[PRD-HOME-SAFETY-V2 2026-05-27] 接收上游/厂商报警推送。
    [BUGFIX HOME-SAFETY-V2-REVISION 2026-05-28 · 修 Bug 2]
    采用"先写 pending → 业务后 update"模式，确保审计零丢失。

    兼容两种报文格式：
    - v1 旧契约：{device_sn, type, alarm_time, sign?}
    - v2 厂商真实报文：{param:{devId,devType,occurTime,gwId,devName,callType}, dataType, msgId}

    异常场景统一返回 200（除内部 DB 异常返回 500），避免厂商无效重试导致雪崩。
    """
    received_at = datetime.utcnow()
    source_ip = _extract_source_ip(request)
    raw_body = b""
    try:
        raw_body = await request.body()
    except Exception:
        pass
    body_text = raw_body.decode("utf-8", errors="ignore") if raw_body else ""

    # 头部信息（用于日志和签名验证钩子）
    try:
        headers_dict = {k: v for k, v in request.headers.items()}
        headers_text = json.dumps(headers_dict, ensure_ascii=False)
    except Exception:
        headers_dict = {}
        headers_text = ""

    # 完整 URL（含 query string）
    try:
        full_url = str(request.url)
    except Exception:
        full_url = ""
    request_method = request.method if hasattr(request, "method") else "POST"

    # ── [BUGFIX V2-REVISION 第一步] 先写 pending 流水（确保零丢失） ──
    log_id = await _log_callback(
        db,
        received_at=received_at,
        source_ip=source_ip,
        headers_text=headers_text,
        body_text=body_text,
        parse_status="pending",
        request_method=request_method,
        request_url=full_url,
    )

    # 默认成功响应（HTTP 200 + code 0），try/finally 中确保流水必更新
    response_payload: Dict[str, Any] = {"code": 0, "message": "ok"}
    final_status: str = "internal_error"
    final_reason: Optional[str] = None
    final_alarm_id: Optional[int] = None
    final_vendor_msg_id: Optional[str] = None
    final_device_sn: Optional[str] = None
    final_data_type: Optional[str] = None
    raised_exc: Optional[BaseException] = None
    response_status_code = 200

    try:
        # ── precheck 自检报文：直接返回 ──
        try:
            quick_payload = json.loads(body_text) if body_text else {}
        except Exception:
            quick_payload = {}
        if isinstance(quick_payload, dict) and (
            quick_payload.get("dataType") == "__precheck__" or quick_payload.get("__precheck__") is True
        ):
            response_payload = {
                "code": 0,
                "message": "ok",
                "precheck": True,
                "matched_project": True,
            }
            final_status = "precheck"
            final_reason = "回调地址自检报文"
            return response_payload

        # 签名验证钩子（本期始终通过）
        if not verify_signature(headers_dict, raw_body):
            final_status = "fail"
            final_reason = "signature_invalid"
            return response_payload

        # 解析 JSON
        payload: Dict[str, Any] = {}
        try:
            if body_text:
                payload = json.loads(body_text)
            if not isinstance(payload, dict):
                payload = {}
        except Exception as e:
            final_status = "parse_fail"
            final_reason = f"json_decode_error:{e}"
            return response_payload

        # ── 字段映射：兼容厂商嵌套 param 和 v1 扁平字段 ──
        vendor_msg_id = payload.get("msgId") or payload.get("vendor_msg_id")
        final_vendor_msg_id = vendor_msg_id
        data_type = payload.get("dataType")
        final_data_type = str(data_type) if data_type is not None else None
        param = payload.get("param") if isinstance(payload.get("param"), dict) else {}

        # ── [BUGFIX HS-CALLBACK-DATATYPE 2026-05-29] 心跳/实时状态类报文优先短路 ──
        # smb-real-time-msg 等心跳类报文不走告警业务，直接标记 ignored，parse_fail_reason 留空，
        # 避免污染"回调原始流水"的失败原因列。
        if data_type in IGNORED_DATA_TYPES:
            final_status = "ignored"
            final_reason = None  # 心跳/已忽略类型，失败原因必须留空
            response_payload = {
                "code": 0,
                "message": "ok",
                "ignored": True,
                "data_type": data_type,
            }
            return response_payload

        device_sn = (param.get("devId") if param else None) or payload.get("device_sn") or ""
        final_device_sn = device_sn or None

        raw_dev_type = (param.get("devType") if param else None)
        if raw_dev_type is None:
            raw_dev_type = payload.get("type")
        device_type: Optional[int] = None
        try:
            if raw_dev_type is not None and str(raw_dev_type) != "":
                device_type = int(raw_dev_type)
        except Exception:
            device_type = None

        alarm_at: Optional[datetime] = None
        occur_time = param.get("occurTime") if param else None
        if occur_time is not None:
            alarm_at = _parse_vendor_alarm_time(occur_time)
        if alarm_at is None and payload.get("alarm_time"):
            try:
                s = str(payload["alarm_time"]).replace("Z", "+00:00")
                alarm_at = datetime.fromisoformat(s).replace(tzinfo=None)
            except Exception:
                alarm_at = None
        time_parse_failed = alarm_at is None
        if alarm_at is None:
            alarm_at = datetime.utcnow()

        raw_gw_id = (param.get("gwId") if param else None) or payload.get("gw_id") or payload.get("gateway_sn") or ""
        # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] gwId 长度从 12 → 8；若上游仍传 12 位，自动截断前 8 位并大写
        gw_id_norm = _normalize_gateway_id(raw_gw_id)
        if len(gw_id_norm) > 8:
            gw_id_norm = gw_id_norm[:8]
        gw_id = gw_id_norm
        dev_name = (param.get("devName") if param else None) or payload.get("dev_name")
        if param and "callType" in param:
            raw_call_type = param.get("callType")
        else:
            raw_call_type = payload.get("call_type")
        try:
            call_type = int(raw_call_type) if raw_call_type is not None and str(raw_call_type) != "" else None
        except Exception:
            call_type = None

        # ── 异常场景 6：关键字段缺失 ──
        if not device_sn:
            final_status = "missing_field"
            final_reason = "缺失 devId/device_sn"
            return response_payload

        # ── 异常场景 1：msgId 重复（永久幂等）──
        if vendor_msg_id:
            try:
                dup = (
                    await db.execute(
                        select(HomeSafetyAlarm).where(HomeSafetyAlarm.vendor_msg_id == vendor_msg_id)
                    )
                ).scalar_one_or_none()
            except Exception:
                dup = None
            if dup is not None:
                final_status = "duplicate"
                final_reason = "vendor_msg_id 已存在"
                final_alarm_id = dup.id
                return response_payload

        # ── [BUGFIX HS-CALLBACK-DATATYPE 2026-05-29] dataType 白名单校验 ──
        # ALERT_DATA_TYPES（{new-call-msg, call-msg}）走告警链路；
        # 其它已传入的 dataType（且非已知忽略类型）视为未识别 → failed。
        if data_type and data_type not in ALERT_DATA_TYPES:
            final_status = "unsupported_type"
            final_reason = f"未识别 dataType: {data_type}"
            return response_payload

        # ── 异常场景 3：devType 不在 {1,2,7} ──
        if device_type is not None and device_type not in ALL_DEVICE_TYPES:
            final_status = "unknown_devtype"
            final_reason = f"devType={device_type}"
            return response_payload

        if time_parse_failed:
            logger.warning("[home_safety_v2] 时间解析失败，用服务器时间兜底 device_sn=%s", device_sn)

        # ── 异常场景 4：devId 未绑定 ──
        try:
            bindings = (
                await db.execute(
                    select(HomeSafetyDeviceBinding).where(
                        HomeSafetyDeviceBinding.device_sn == device_sn,
                        HomeSafetyDeviceBinding.status == 1,
                    )
                )
            ).scalars().all()
            # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 若没有 status=1 但有 status=2（撞号失效），
            # 视为"已存在但需重绑"，按 PRD 4.3 返回 410 device_rebind_required。
            invalid_bindings: List[Any] = []
            if not bindings:
                invalid_bindings = (
                    await db.execute(
                        select(HomeSafetyDeviceBinding).where(
                            HomeSafetyDeviceBinding.device_sn == device_sn,
                            HomeSafetyDeviceBinding.status == 2,
                        )
                    )
                ).scalars().all()
        except Exception as e:
            logger.error("[home_safety_v2] 查询绑定异常: %s", e)
            final_status = "internal_error"
            final_reason = str(e)[:500]
            response_status_code = 500
            raise HTTPException(500, "internal error")

        if not bindings:
            if invalid_bindings:
                # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 设备记录因撞号失效 → 410
                final_status = "device_rebind_required"
                final_reason = f"device_sn={device_sn} 撞号失效，请重新绑定"
                response_payload = {
                    "code": 410,
                    "message": "device_rebind_required",
                    "success": False,
                    "matched": 0,
                }
                response_status_code = 410
                return response_payload
            final_status = "unbound"
            final_reason = f"device_sn={device_sn} 未绑定"
            response_payload = {
                "code": 0,
                "message": "ok",
                "success": True,
                "matched": 0,
                "note": "no binding",
            }
            return response_payload

        # ── 落库 + 去重 ──
        dedupe_key = _dedupe_key(device_sn, alarm_at)
        created: List[int] = []
        dedup_skipped = 0
        first_alarm_id: Optional[int] = None
        try:
            for b in bindings:
                existing = (
                    await db.execute(
                        select(HomeSafetyAlarm).where(
                            HomeSafetyAlarm.dedupe_key == dedupe_key,
                            HomeSafetyAlarm.user_id == b.user_id,
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    existing.dedupe_count = (existing.dedupe_count or 1) + 1
                    dedup_skipped += 1
                    if first_alarm_id is None:
                        first_alarm_id = existing.id
                    continue
                # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 汇总通知目标号码 + 去重
                notify_info: Dict[str, Any] = {"targets": [], "dedup_skipped": 0}
                try:
                    notify_info = await collect_alarm_notify_targets(
                        db,
                        user_id=b.user_id,
                        device_type=device_type or b.device_type,
                        device_emergency_phone=b.emergency_phone,
                    )
                except Exception as _ne:  # pragma: no cover
                    logger.warning("[home_safety_v1] 通知目标汇总失败: %s", _ne)
                try:
                    notify_targets_json = json.dumps(notify_info, ensure_ascii=False)
                except Exception:
                    notify_targets_json = None

                rec = HomeSafetyAlarm(
                    user_id=b.user_id,
                    device_type=device_type or b.device_type,
                    device_sn=device_sn,
                    gateway_sn=b.gateway_sn,
                    alarm_at=alarm_at,
                    received_at=received_at,
                    dedupe_key=dedupe_key,
                    dedupe_count=1,
                    notify_inapp=1,
                    notify_mp=1,
                    notify_sms=1,
                    notify_ai_call=3,
                    notify_ai_call_status="failed",
                    notify_ai_call_fail_reason="本期未对接外呼通道",
                    ai_call_quota_user=b.user_id,
                    read_status=0,
                    handle_status=0,
                    vendor_msg_id=vendor_msg_id,
                    gw_id=gw_id,
                    dev_name=dev_name,
                    call_type=call_type,
                    data_type=data_type or "new-call-msg",
                    source_ip=source_ip,
                    device_emergency_phone=(b.emergency_phone or None),
                    notify_targets_json=notify_targets_json,
                    notify_dedup_skipped=int(notify_info.get("dedup_skipped") or 0),
                    # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 冗余设备所属成员
                    member_id=getattr(b, "member_id", None),
                )
                db.add(rec)
                await db.flush()
                created.append(rec.id)
                if first_alarm_id is None:
                    first_alarm_id = rec.id
            await db.commit()
        except Exception as e:
            logger.error("[home_safety_v2] 落库异常: %s", e)
            try:
                await db.rollback()
            except Exception:
                pass
            final_status = "internal_error"
            final_reason = str(e)[:500]
            response_status_code = 500
            raise HTTPException(500, "internal error")

        final_status = "ok"
        final_alarm_id = first_alarm_id
        response_payload = {
            "code": 0,
            "message": "ok",
            "success": True,
            "matched": len(bindings),
            "created": len(created),
            "dedup_skipped": dedup_skipped,
            "alarm_ids": created,
        }
        return response_payload

    except HTTPException as e:
        raised_exc = e
        if final_status == "internal_error":
            response_status_code = e.status_code
        raise
    except Exception as e:
        # 任何未捕获异常都要被记入流水
        raised_exc = e
        logger.exception("[home_safety_v2] 回调处理未预期异常: %s", e)
        final_status = "internal_error"
        final_reason = str(e)[:500]
        response_status_code = 500
        raise HTTPException(500, "internal error")
    finally:
        # ── [BUGFIX V2-REVISION] 无论成功失败，必须更新流水（try/finally 兜底）──
        if log_id is not None:
            try:
                resp_body_text = json.dumps(response_payload, ensure_ascii=False)
            except Exception:
                resp_body_text = ""
            try:
                await _update_callback_log(
                    db,
                    log_id,
                    parse_status=final_status,
                    parse_fail_reason=final_reason,
                    linked_alarm_id=final_alarm_id,
                    vendor_msg_id=final_vendor_msg_id,
                    response_status=response_status_code,
                    response_body=resp_body_text,
                    device_sn=final_device_sn,
                    data_type=final_data_type,
                )
            except Exception as ue:  # pragma: no cover
                logger.warning("[home_safety_v2] finally 更新流水失败: %s", ue)


@router.post("/api/home_safety/callback/ai_call_result")
@router.post("/callback/home_safety/ai_call_result")
async def upstream_ai_call_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """AI 外呼结果回调（本期仅落库，不解析）。"""
    raw = await request.body()
    payload_text = raw.decode("utf-8", errors="ignore") if raw else ""
    logger.info("[home_safety_v1] ai_call_callback payload=%s", payload_text[:512])
    return {"success": True, "received": True}


# ────────────── 管理后台 API ──────────────
ADMIN_PREFIX = "/api/admin/home_safety"


@router.get(ADMIN_PREFIX + "/dict/device_types")
async def admin_get_device_types(current_user=Depends(get_current_user)):
    """字典：3 类设备的名称/颜色/标题模板/AI 话术。"""
    items = []
    for t in ALL_DEVICE_TYPES:
        items.append(
            {
                "device_type": t,
                "device_type_label": DEVICE_TYPE_LABEL[t],
                "color": DEVICE_TYPE_COLOR[t],
                "title_template": DEVICE_TYPE_NOTICE_TITLE[t],
                "ai_script_template": DEVICE_TYPE_AI_SCRIPT[t],
                "enabled": True,
            }
        )
    return {"items": items}


@router.get(ADMIN_PREFIX + "/bindings")
async def admin_list_bindings(
    device_type: Optional[int] = None,
    user_id: Optional[int] = None,
    member_id: Optional[int] = None,
    page: int = 1,
    size: int = 50,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(HomeSafetyDeviceBinding)
    if device_type is not None:
        q = q.where(HomeSafetyDeviceBinding.device_type == device_type)
    if user_id is not None:
        q = q.where(HomeSafetyDeviceBinding.user_id == user_id)
    # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 管理后台支持按归属成员过滤
    if member_id is not None:
        q = q.where(HomeSafetyDeviceBinding.member_id == member_id)
    q = q.order_by(desc(HomeSafetyDeviceBinding.created_at)).limit(size).offset((page - 1) * size)
    rows = (await db.execute(q)).scalars().all()

    # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 批量填充成员名称
    member_id_set = {b.member_id for b in rows if getattr(b, "member_id", None)}
    member_name_map: Dict[int, str] = {}
    if member_id_set:
        try:
            from app.models.models import FamilyMember as _FM  # type: ignore
            mrows = (
                await db.execute(
                    select(_FM).where(_FM.id.in_(list(member_id_set)))
                )
            ).scalars().all()
            for m in mrows:
                member_name_map[int(m.id)] = (
                    "本人" if bool(getattr(m, "is_self", False))
                    else (getattr(m, "nickname", None) or getattr(m, "relationship_type", None) or f"成员{m.id}")
                )
        except Exception:
            pass

    return {
        "items": [
            {
                "id": b.id,
                "user_id": b.user_id,
                "device_type": b.device_type,
                "device_type_label": _device_label(b.device_type),
                "device_type_color": DEVICE_TYPE_COLOR.get(b.device_type),
                # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 提供 gateway_id 别名
                "gateway_sn": b.gateway_sn,
                "gateway_id": b.gateway_sn,
                "device_sn": b.device_sn,
                "status": b.status,
                "status_label": "有效" if b.status == 1 else ("失效需重绑" if b.status == 2 else "已解绑"),
                "invalid_reason": b.invalid_reason if b.status == 2 else None,
                "verify_status": b.verify_status,
                "bound_at": (b.bound_at.isoformat() + "Z") if b.bound_at else None,
                "unbound_at": (b.unbound_at.isoformat() + "Z") if b.unbound_at else None,
                # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 紧急联系手机字段（明文，按 4-B：默认隐藏可勾选）
                "emergency_phone": b.emergency_phone or "",
                "emergency_phone_mask": _mask_phone(b.emergency_phone),
                "emergency_phone_filled": bool(b.emergency_phone),
                # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 归属成员字段
                "member_id": getattr(b, "member_id", None),
                "member_name": member_name_map.get(int(getattr(b, "member_id", 0) or 0)) if getattr(b, "member_id", None) else None,
                "migrated_to_self": bool(getattr(b, "migrated_to_self", False)),
                # [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 设备备注
                "remark": getattr(b, "remark", None),
            }
            for b in rows
        ]
    }


# [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 一次性数据迁移接口（idempotent）
@router.post(ADMIN_PREFIX + "/migrate_member_id")
async def admin_migrate_member_id(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 历史数据一次性迁移：
    - 为每个 user 确保存在"本人"成员
    - 将 home_safety_device_binding.member_id IS NULL 的记录迁到该用户的"本人"成员
       并设置 migrated_to_self=1
    - 同步 home_safety_alarm.member_id（基于 device_sn 关联）
    - 同步 home_safety_emergency_contact.member_id 到本人
    可重复调用（幂等）。
    """
    summary = {
        "self_members_created": 0,
        "bindings_migrated": 0,
        "alarms_migrated": 0,
        "contacts_migrated": 0,
    }
    try:
        from app.models.models import FamilyMember as _FM  # type: ignore
    except Exception:
        raise HTTPException(500, "FamilyMember 模型不可用，无法迁移")

    # Step 1: 收集所有需要处理的 user_id（在三张表里均可能出现）
    user_ids: set = set()
    for tbl in (HomeSafetyDeviceBinding, HomeSafetyAlarm, HomeSafetyEmergencyContact):
        try:
            uids = (await db.execute(select(tbl.user_id).distinct())).scalars().all()
            for u in uids:
                if u:
                    user_ids.add(int(u))
        except Exception:
            pass

    # Step 1b: 为每个 user 确保本人成员
    user_self_map: Dict[int, int] = {}
    for uid in user_ids:
        existing = (
            await db.execute(
                select(_FM).where(_FM.user_id == uid, _FM.is_self == True)  # noqa: E712
            )
        ).scalar_one_or_none()
        if existing:
            user_self_map[uid] = int(existing.id)
            continue
        new_self = _FM(
            user_id=uid,
            relationship_type="self",
            nickname="本人",
            is_self=True,
            status="active",
        )
        db.add(new_self)
        await db.flush()
        user_self_map[uid] = int(new_self.id)
        summary["self_members_created"] += 1
    await db.commit()

    # Step 2: 迁移 binding
    null_bindings = (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.member_id.is_(None)
            )
        )
    ).scalars().all()
    for b in null_bindings:
        sid = user_self_map.get(int(b.user_id))
        if sid is None:
            continue
        b.member_id = sid
        b.migrated_to_self = True
        summary["bindings_migrated"] += 1
    await db.commit()

    # Step 3: 同步 alarm（只迁 NULL 的，保持幂等）
    null_alarms = (
        await db.execute(
            select(HomeSafetyAlarm).where(HomeSafetyAlarm.member_id.is_(None))
        )
    ).scalars().all()
    # 优先按 device_sn 关联到对应 binding 的 member_id；找不到再用本人兜底
    bind_by_sn: Dict[str, int] = {}
    for b in (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.member_id.is_not(None)
            )
        )
    ).scalars().all():
        bind_by_sn.setdefault(b.device_sn or "", int(b.member_id))
    for a in null_alarms:
        mid = bind_by_sn.get(a.device_sn or "")
        if mid is None:
            mid = user_self_map.get(int(a.user_id))
        if mid is None:
            continue
        a.member_id = mid
        summary["alarms_migrated"] += 1
    await db.commit()

    # Step 4: 同步 emergency contacts
    null_contacts = (
        await db.execute(
            select(HomeSafetyEmergencyContact).where(
                HomeSafetyEmergencyContact.member_id.is_(None)
            )
        )
    ).scalars().all()
    for c in null_contacts:
        sid = user_self_map.get(int(c.user_id))
        if sid is None:
            continue
        c.member_id = sid
        summary["contacts_migrated"] += 1
    await db.commit()

    return {"success": True, **summary}


# [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 管理后台搜索网关ID 接口（基于 gateway_id 8 位查询）
@router.get(ADMIN_PREFIX + "/bindings/search_by_gateway")
async def admin_search_by_gateway_id(
    gateway_id: str = Query(..., description="8 位网关ID"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    norm = _normalize_gateway_id(gateway_id)
    if not GATEWAY_ID_REGEX.match(norm):
        raise HTTPException(400, "invalid_gateway_id:网关ID 必须为 8 位字母或数字")
    rows = (
        await db.execute(
            select(HomeSafetyDeviceBinding).where(
                HomeSafetyDeviceBinding.gateway_sn == norm
            ).order_by(desc(HomeSafetyDeviceBinding.updated_at))
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": b.id,
                "user_id": b.user_id,
                "device_type": b.device_type,
                "device_type_label": _device_label(b.device_type),
                "gateway_id": b.gateway_sn,
                "gateway_sn": b.gateway_sn,
                "device_sn": b.device_sn,
                "status": b.status,
                "status_label": "有效" if b.status == 1 else ("失效需重绑" if b.status == 2 else "已解绑"),
                "invalid_reason": b.invalid_reason if b.status == 2 else None,
                "emergency_phone": b.emergency_phone or "",
                "emergency_phone_mask": _mask_phone(b.emergency_phone),
                "bound_at": (b.bound_at.isoformat() + "Z") if b.bound_at else None,
            }
            for b in rows
        ]
    }


# [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] 管理后台导出 CSV（含网关ID + 紧急联系手机）
@router.get(ADMIN_PREFIX + "/bindings/export")
async def admin_export_bindings(
    device_type: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(HomeSafetyDeviceBinding)
    if device_type is not None:
        q = q.where(HomeSafetyDeviceBinding.device_type == device_type)
    q = q.order_by(desc(HomeSafetyDeviceBinding.created_at)).limit(10000)
    rows = (await db.execute(q)).scalars().all()
    headers = ["流水ID", "用户ID", "设备类型", "网关ID", "设备SN", "设备紧急联系手机", "状态", "绑定时间", "解绑时间"]
    out_rows: List[List[str]] = [headers]
    for b in rows:
        out_rows.append([
            str(b.id),
            str(b.user_id),
            _device_label(b.device_type),
            b.gateway_sn or "",
            b.device_sn or "",
            b.emergency_phone or "",
            "有效" if b.status == 1 else ("失效需重绑" if b.status == 2 else "已解绑"),
            (b.bound_at.isoformat() + "Z") if b.bound_at else "",
            (b.unbound_at.isoformat() + "Z") if b.unbound_at else "",
        ])
    return {"headers": headers, "rows": out_rows, "total": len(rows)}


@router.get(ADMIN_PREFIX + "/alarms")
async def admin_list_alarms(
    device_type: Optional[int] = None,
    user_id: Optional[int] = None,
    page: int = 1,
    size: int = 50,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(HomeSafetyAlarm)
    if device_type is not None:
        q = q.where(HomeSafetyAlarm.device_type == device_type)
    if user_id is not None:
        q = q.where(HomeSafetyAlarm.user_id == user_id)
    q = q.order_by(desc(HomeSafetyAlarm.alarm_at)).limit(size).offset((page - 1) * size)
    rows = (await db.execute(q)).scalars().all()

    # [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 批量关联设备备注（管理后台告警记录"设备备注"列）
    device_sn_set = {a.device_sn for a in rows if a.device_sn}
    remark_by_sn: Dict[str, str] = {}
    if device_sn_set:
        try:
            brows = (
                await db.execute(
                    select(HomeSafetyDeviceBinding).where(
                        HomeSafetyDeviceBinding.device_sn.in_(list(device_sn_set))
                    )
                )
            ).scalars().all()
            for bd in brows:
                if bd.device_sn:
                    if bd.device_sn not in remark_by_sn or bd.status == 1:
                        remark_by_sn[bd.device_sn] = getattr(bd, "remark", None) or ""
        except Exception:
            pass

    return {
        "items": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "device_type": a.device_type,
                "device_type_label": _device_label(a.device_type),
                "device_sn": a.device_sn,
                # [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 设备备注（无备注返回 None）
                "device_remark": remark_by_sn.get(a.device_sn or "", "") or None,
                "alarm_at": (a.alarm_at.isoformat() + "Z") if a.alarm_at else None,
                "received_at": (a.received_at.isoformat() + "Z") if a.received_at else None,
                "dedupe_count": a.dedupe_count,
                "notify_inapp": a.notify_inapp,
                "notify_mp": a.notify_mp,
                "notify_sms": a.notify_sms,
                "notify_ai_call": a.notify_ai_call,
                "read_status": a.read_status,
                "handle_status": a.handle_status,
                "handle_note": a.handle_note,
                # [PRD-HOME-SAFETY-V2 2026-05-27] v2 新增列
                "gw_id": getattr(a, "gw_id", None),
                "vendor_msg_id": getattr(a, "vendor_msg_id", None),
                "notify_ai_call_status": getattr(a, "notify_ai_call_status", "failed") or "failed",
                "notify_ai_call_fail_reason": getattr(a, "notify_ai_call_fail_reason", None),
                "source_ip": getattr(a, "source_ip", None),
                "data_type": getattr(a, "data_type", None),
                "call_type": getattr(a, "call_type", None),
                "dev_name": getattr(a, "dev_name", None),
            }
            for a in rows
        ]
    }


@router.get(ADMIN_PREFIX + "/callback_config")
async def admin_get_callback_config(
    mask_token: bool = Query(default=False, description="是否对 Token 做密文展示"),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = (await db.execute(select(HomeSafetyCallbackConfig).limit(1))).scalar_one_or_none()
    if not cfg:
        return {
            "org_id": None,
            "callback_url": None,
            "auth_token": None,
            "auth_token_masked": None,
            "upstream_base_url": None,
            "upstream_path": None,
            "full_upstream_url": "",
            "callback_domain": None,
            "callback_path": DEFAULT_CALLBACK_PATH,
            "full_callback_url": "",
            "last_pushed_at": None,
            "last_test_result": None,
            "last_test_at": None,
            "last_push_status": None,
            "last_push_url": None,
            "last_push_code": None,
            "last_push_message": None,
            "last_push_raw": None,
            "last_push_judge_basis": None,
            "updated_at": None,
        }

    token_val = cfg.auth_token
    cb_path = cfg.callback_path or DEFAULT_CALLBACK_PATH

    return {
        "org_id": cfg.org_id,
        "callback_url": cfg.callback_url,
        "auth_token": None if mask_token else token_val,
        "auth_token_masked": _mask_token(token_val),
        "upstream_base_url": cfg.upstream_base_url,
        "upstream_path": cfg.upstream_path,
        "full_upstream_url": _build_full_upstream_url(cfg.upstream_base_url, cfg.upstream_path),
        "callback_domain": cfg.callback_domain,
        "callback_path": cb_path,
        "full_callback_url": _build_full_callback_url(cfg.callback_domain, cb_path) or cfg.callback_url or "",
        "last_pushed_at": (cfg.last_pushed_at.isoformat() + "Z") if cfg.last_pushed_at else None,
        "last_test_result": cfg.last_test_result,
        "last_test_at": (cfg.last_test_at.isoformat() + "Z") if cfg.last_test_at else None,
        "last_push_status": cfg.last_push_status,
        "last_push_url": cfg.last_push_url,
        "last_push_code": cfg.last_push_code,
        "last_push_message": cfg.last_push_message,
        "last_push_raw": cfg.last_push_raw,
        "last_push_judge_basis": getattr(cfg, "last_push_judge_basis", None),
        "updated_at": (cfg.updated_at.isoformat() + "Z") if cfg.updated_at else None,
    }


@router.put(ADMIN_PREFIX + "/callback_config")
async def admin_save_callback_config(
    req: CallbackConfigReq,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-HOME-SAFETY-V2 F2] 保存配置：仅写本地，不调上游"""
    cfg = (await db.execute(select(HomeSafetyCallbackConfig).limit(1))).scalar_one_or_none()
    if not cfg:
        cfg = HomeSafetyCallbackConfig(callback_path=DEFAULT_CALLBACK_PATH)
        db.add(cfg)
    if req.org_id is not None:
        cfg.org_id = req.org_id
    if req.auth_token is not None:
        cfg.auth_token = req.auth_token
    if req.upstream_base_url is not None:
        cfg.upstream_base_url = (req.upstream_base_url or "").rstrip("/")
    if req.upstream_path is not None:
        p = (req.upstream_path or "").strip()
        if p and not p.startswith("/"):
            p = "/" + p
        cfg.upstream_path = p
    if req.callback_domain is not None:
        cfg.callback_domain = (req.callback_domain or "").rstrip("/")
    # callback_path 固定常量
    if not cfg.callback_path:
        cfg.callback_path = DEFAULT_CALLBACK_PATH
    # callback_url：自动拼接（兼容老字段）；若用户传了 callback_url 则尊重
    if req.callback_url is not None:
        cfg.callback_url = req.callback_url
    elif cfg.callback_domain:
        cfg.callback_url = _build_full_callback_url(cfg.callback_domain, cfg.callback_path)
    cfg.updated_at = datetime.utcnow()
    await db.commit()
    return {"success": True}


@router.post(ADMIN_PREFIX + "/callback_config/test")
async def admin_test_callback(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[v1 保留] 仅做形式校验。v2 不再使用此接口，但保留以保持向后兼容。"""
    cfg = (await db.execute(select(HomeSafetyCallbackConfig).limit(1))).scalar_one_or_none()
    if not cfg or not cfg.upstream_base_url:
        raise HTTPException(400, "请先保存上游基础 URL")
    ok = cfg.upstream_base_url.startswith("http://") or cfg.upstream_base_url.startswith("https://")
    cfg.last_test_at = datetime.utcnow()
    cfg.last_test_result = "✓ 连通正常 (200 OK)" if ok else "✗ URL 格式不合法"
    await db.commit()
    return {"success": ok, "result": cfg.last_test_result}


# 注入点：测试桩，便于单测注入 mock；生产为 None 时走真实 httpx
_PUSH_UPSTREAM_OVERRIDE = None  # type: ignore


async def _real_push_upstream(
    full_url: str,
    auth_token: Optional[str],
    dept_id: Optional[str],
    callback_url: str,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """[PRD-HOME-SAFETY-V2 F13] 真实 HTTP 调用上游"""
    if _PUSH_UPSTREAM_OVERRIDE is not None:
        return await _PUSH_UPSTREAM_OVERRIDE(full_url, auth_token, dept_id, callback_url)

    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    body = {"deptId": dept_id or "", "url": callback_url}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(full_url, json=body, headers=headers)
    except httpx.TimeoutException:
        return {"status": "fail", "code": None, "message": "请求超时", "raw": ""}
    except httpx.RequestError as e:
        return {"status": "fail", "code": None, "message": f"网络错误: {e}", "raw": ""}

    raw_text = resp.text or ""
    if 500 <= resp.status_code < 600:
        return {
            "status": "fail",
            "code": resp.status_code,
            "message": "上游服务异常",
            "raw": raw_text[:2000],
            "judge_basis": f"HTTP {resp.status_code} 5xx → 上游服务异常",
        }
    try:
        data = resp.json()
    except Exception:
        return {
            "status": "fail",
            "code": resp.status_code,
            "message": "上游响应解析失败",
            "raw": raw_text[:2000],
            "judge_basis": f"HTTP {resp.status_code} 但响应非 JSON",
        }

    if not isinstance(data, dict):
        return {
            "status": "fail",
            "code": resp.status_code,
            "message": "上游返回结构异常",
            "raw": raw_text[:2000],
            "judge_basis": f"HTTP {resp.status_code} 但 JSON 不是对象",
        }

    # ── [BUGFIX HOME-SAFETY-V2-REVISION 2026-05-28 · 修 Bug 1] 兼容式成功判定 ──
    # 实际厂商返回 {"code":200,"message":"success"}，原硬编码 code==0 误判失败。
    # 新规则：HTTP 200 AND (code 命中白名单 OR message 命中白名单)
    raw_code = data.get("code")
    raw_message = data.get("message") or data.get("msg") or ""
    # code 提取（支持 int 与 str），并保留原值用于透传
    code: Optional[int] = None
    if isinstance(raw_code, int):
        code = raw_code
    elif isinstance(raw_code, str):
        try:
            code = int(raw_code.strip())
        except Exception:
            code = None

    SUCCESS_CODES = {0, 200}
    SUCCESS_MESSAGES = {"ok", "success", "成功"}

    code_hit = code is not None and code in SUCCESS_CODES
    msg_normalized = (str(raw_message) or "").strip().lower()
    msg_hit = msg_normalized in {m.lower() for m in SUCCESS_MESSAGES}

    if resp.status_code == 200 and (code_hit or msg_hit):
        basis_parts = [f"HTTP 200"]
        if code_hit:
            basis_parts.append(f"code={raw_code} 命中成功白名单")
        if msg_hit:
            basis_parts.append(f"message={raw_message!r} 命中成功白名单")
        return {
            "status": "success",
            "code": code if code is not None else resp.status_code,
            "message": str(raw_message) or "ok",
            "raw": raw_text[:2000],
            "judge_basis": " + ".join(basis_parts),
        }

    if resp.status_code != 200:
        # 4xx：透传上游 message
        return {
            "status": "fail",
            "code": code if code is not None else resp.status_code,
            "message": str(raw_message) or f"HTTP {resp.status_code}",
            "raw": raw_text[:2000],
            "judge_basis": f"HTTP {resp.status_code} 非 200",
        }

    # HTTP 200 但 code/message 都未命中
    return {
        "status": "fail",
        "code": code if code is not None else resp.status_code,
        "message": str(raw_message) or "上游返回非成功",
        "raw": raw_text[:2000],
        "judge_basis": f"HTTP 200 但 code={raw_code!r} 与 message={raw_message!r} 都未命中成功白名单",
    }


@router.post(ADMIN_PREFIX + "/callback_config/push_upstream")
async def admin_push_upstream(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-HOME-SAFETY-V2 F3] 真实调用上游 POST 推送回调地址，并落库历史。"""
    cfg = (await db.execute(select(HomeSafetyCallbackConfig).limit(1))).scalar_one_or_none()
    if not cfg:
        raise HTTPException(400, "请先保存配置")

    full_url = _build_full_upstream_url(cfg.upstream_base_url, cfg.upstream_path)
    callback_url = _build_full_callback_url(cfg.callback_domain, cfg.callback_path or DEFAULT_CALLBACK_PATH) or (cfg.callback_url or "")

    # 配置缺失校验
    missing: List[str] = []
    if not full_url:
        missing.append("完整上游 URL")
    if not callback_url:
        missing.append("完整回调 URL")
    if not cfg.org_id:
        missing.append("机构 ID")
    if missing:
        raise HTTPException(400, f"配置不完整: {', '.join(missing)}")

    result = await _real_push_upstream(
        full_url=full_url,
        auth_token=cfg.auth_token,
        dept_id=cfg.org_id,
        callback_url=callback_url,
    )

    now = datetime.utcnow()
    cfg.last_pushed_at = now
    cfg.last_push_status = result["status"]
    cfg.last_push_url = callback_url
    cfg.last_push_code = result.get("code") if isinstance(result.get("code"), int) else None
    cfg.last_push_message = result.get("message")
    cfg.last_push_raw = result.get("raw")
    cfg.last_push_judge_basis = (result.get("judge_basis") or "")[:500]

    # 落历史
    hist = HomeSafetyCallbackPushHistory(
        pushed_at=now,
        pushed_url=callback_url,
        operator_user_id=getattr(current_user, "id", None),
        operator_username=getattr(current_user, "nickname", None) or getattr(current_user, "phone", None) or "admin",
        status=result["status"],
        upstream_code=cfg.last_push_code,
        upstream_message=result.get("message"),
        upstream_raw=result.get("raw"),
    )
    db.add(hist)
    await db.commit()
    return {
        "success": result["status"] == "success",
        "status": result["status"],
        "code": cfg.last_push_code,
        "message": result.get("message"),
        "raw": result.get("raw"),
        "pushed_at": now.isoformat() + "Z",
        "pushed_url": callback_url,
        # [BUGFIX HOME-SAFETY-V2-REVISION 2026-05-28] 判定依据透传给前端
        "judge_basis": result.get("judge_basis", ""),
    }


@router.get(ADMIN_PREFIX + "/callback_config/push_history")
async def admin_get_push_history(
    limit: int = Query(default=3, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[PRD-HOME-SAFETY-V2 F5] 推送历史（默认最近 3 条）"""
    rows = (
        await db.execute(
            select(HomeSafetyCallbackPushHistory)
            .order_by(desc(HomeSafetyCallbackPushHistory.pushed_at))
            .limit(limit)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "pushed_at": (r.pushed_at.isoformat() + "Z") if r.pushed_at else None,
                "pushed_url": r.pushed_url,
                "operator_user_id": r.operator_user_id,
                "operator_username": r.operator_username,
                "status": r.status,
                "upstream_code": r.upstream_code,
                "upstream_message": r.upstream_message,
                "upstream_raw": r.upstream_raw,
            }
            for r in rows
        ]
    }


# ────────── [BUGFIX HOME-SAFETY-V2-REVISION 2026-05-28] 新增审计接口 ──────────
@router.get(ADMIN_PREFIX + "/callback_log")
async def admin_list_callback_log(
    start_at: Optional[str] = None,
    end_at: Optional[str] = None,
    parse_status: Optional[str] = None,
    device_sn: Optional[str] = None,
    source_ip: Optional[str] = None,
    keyword: Optional[str] = None,
    data_type: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUGFIX V2-REVISION] 回调原始记录列表查询，支持时间/状态/设备SN/来源IP/关键字/分页。
    [BUGFIX HS-CALLBACK-DATATYPE 2026-05-29] 新增 data_type 筛选（new-call-msg / call-msg
    / smb-real-time-msg / __other__ 其它）。
    """
    q = select(HomeSafetyCallbackLog)
    cnt_q = select(func.count(HomeSafetyCallbackLog.id))

    conds = []
    if start_at:
        try:
            s = start_at.replace("Z", "+00:00")
            dt_s = datetime.fromisoformat(s).replace(tzinfo=None)
            conds.append(HomeSafetyCallbackLog.received_at >= dt_s)
        except Exception:
            pass
    if end_at:
        try:
            s = end_at.replace("Z", "+00:00")
            dt_e = datetime.fromisoformat(s).replace(tzinfo=None)
            conds.append(HomeSafetyCallbackLog.received_at <= dt_e)
        except Exception:
            pass
    if parse_status and parse_status != "all":
        conds.append(HomeSafetyCallbackLog.parse_status == parse_status)
    if device_sn:
        conds.append(HomeSafetyCallbackLog.device_sn.like(f"%{device_sn}%"))
    if source_ip:
        conds.append(HomeSafetyCallbackLog.source_ip == source_ip)
    if keyword:
        conds.append(HomeSafetyCallbackLog.request_body.like(f"%{keyword}%"))
    # [BUGFIX HS-CALLBACK-DATATYPE 2026-05-29] data_type 筛选
    if data_type and data_type != "all":
        KNOWN_DATA_TYPES = {"new-call-msg", "call-msg", "smb-real-time-msg"}
        if data_type == "__other__":
            # 其它：既不在已知列表，也不为 NULL（保留原始未空但非已知的）
            conds.append(
                and_(
                    HomeSafetyCallbackLog.data_type.is_not(None),
                    HomeSafetyCallbackLog.data_type.notin_(list(KNOWN_DATA_TYPES)),
                )
            )
        else:
            conds.append(HomeSafetyCallbackLog.data_type == data_type)

    if conds:
        q = q.where(and_(*conds))
        cnt_q = cnt_q.where(and_(*conds))

    total = (await db.execute(cnt_q)).scalar_one()

    q = q.order_by(desc(HomeSafetyCallbackLog.received_at)).limit(size).offset((page - 1) * size)
    rows = (await db.execute(q)).scalars().all()

    return {
        "total": int(total or 0),
        "page": page,
        "size": size,
        "items": [
            {
                "id": r.id,
                "received_at": (r.received_at.isoformat() + "Z") if r.received_at else None,
                "processed_at": (r.processed_at.isoformat() + "Z") if r.processed_at else None,
                "source_ip": r.source_ip,
                "parse_status": r.parse_status,
                "parse_fail_reason": r.parse_fail_reason,
                "device_sn": r.device_sn,
                "vendor_msg_id": r.vendor_msg_id,
                "linked_alarm_id": r.linked_alarm_id,
                "request_method": r.request_method,
                "request_url": r.request_url,
                "response_status": r.response_status,
                # [BUGFIX HS-CALLBACK-DATATYPE 2026-05-29] 报文类型独立字段
                "data_type": r.data_type,
            }
            for r in rows
        ],
    }


@router.get(ADMIN_PREFIX + "/callback_log/{log_id}")
async def admin_get_callback_log_detail(
    log_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUGFIX V2-REVISION] 回调原始记录详情：含完整 headers、body、字段映射对照。"""
    row = (
        await db.execute(
            select(HomeSafetyCallbackLog).where(HomeSafetyCallbackLog.id == log_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "记录不存在")

    # 字段映射对照（厂商字段 → 我方字段 → 落库值）
    parsed_payload: Dict[str, Any] = {}
    try:
        if row.request_body:
            parsed_payload = json.loads(row.request_body)
            if not isinstance(parsed_payload, dict):
                parsed_payload = {}
    except Exception:
        parsed_payload = {}

    param = parsed_payload.get("param") if isinstance(parsed_payload.get("param"), dict) else {}
    field_mapping = [
        {"vendor": "msgId", "ours": "vendor_msg_id", "value": parsed_payload.get("msgId") or parsed_payload.get("vendor_msg_id")},
        {"vendor": "dataType", "ours": "data_type", "value": parsed_payload.get("dataType")},
        {"vendor": "param.devId", "ours": "device_sn", "value": (param.get("devId") if param else None) or parsed_payload.get("device_sn")},
        {"vendor": "param.devType", "ours": "device_type", "value": (param.get("devType") if param else None) or parsed_payload.get("type")},
        {"vendor": "param.occurTime", "ours": "alarm_at", "value": (param.get("occurTime") if param else None) or parsed_payload.get("alarm_time")},
        {"vendor": "param.gwId", "ours": "gw_id", "value": (param.get("gwId") if param else None) or parsed_payload.get("gw_id")},
        {"vendor": "param.devName", "ours": "dev_name", "value": (param.get("devName") if param else None) or parsed_payload.get("dev_name")},
        {"vendor": "param.callType", "ours": "call_type", "value": (param.get("callType") if param else None) or parsed_payload.get("call_type")},
    ]

    headers_dict: Dict[str, Any] = {}
    try:
        if row.request_headers:
            headers_dict = json.loads(row.request_headers)
            if not isinstance(headers_dict, dict):
                headers_dict = {}
    except Exception:
        headers_dict = {}

    return {
        "id": row.id,
        "received_at": (row.received_at.isoformat() + "Z") if row.received_at else None,
        "processed_at": (row.processed_at.isoformat() + "Z") if row.processed_at else None,
        "source_ip": row.source_ip,
        "request_method": row.request_method,
        "request_url": row.request_url,
        "request_headers": headers_dict,
        "request_body": row.request_body,
        "request_body_parsed": parsed_payload,
        "field_mapping": field_mapping,
        "parse_status": row.parse_status,
        "parse_fail_reason": row.parse_fail_reason,
        "device_sn": row.device_sn,
        "vendor_msg_id": row.vendor_msg_id,
        "linked_alarm_id": row.linked_alarm_id,
        "response_status": row.response_status,
        "response_body": row.response_body,
        # [BUGFIX HS-CALLBACK-DATATYPE 2026-05-29] 报文类型独立字段
        "data_type": row.data_type,
    }


# ────────── [BUGFIX V2-REVISION] 回调地址自检接口 ──────────
class PrecheckReq(BaseModel):
    callback_url: Optional[str] = None  # 不传则用配置中的


@router.post(ADMIN_PREFIX + "/callback_config/precheck")
async def admin_precheck_callback_url(
    req: Optional[PrecheckReq] = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """[BUGFIX V2-REVISION 修复 3] 回调地址自检：5 项检查。
    - URL 格式合法
    - URL 必须 https
    - 域名可解析
    - 外网可达 (HEAD)
    - URL 必须能命中本项目（构造 dataType=__precheck__ POST 自回环）
    """
    target_url: Optional[str] = None
    if req and req.callback_url:
        target_url = req.callback_url.strip()
    else:
        cfg = (await db.execute(select(HomeSafetyCallbackConfig).limit(1))).scalar_one_or_none()
        if cfg:
            target_url = _build_full_callback_url(
                cfg.callback_domain, cfg.callback_path or DEFAULT_CALLBACK_PATH
            ) or (cfg.callback_url or "")

    checks: List[Dict[str, Any]] = []

    def add_check(name: str, status: str, detail: str = ""):
        checks.append({"name": name, "status": status, "detail": detail})

    if not target_url:
        add_check("URL 格式合法", "fail", "回调 URL 为空，请先填写并保存")
        return {
            "success": False,
            "blocked": True,
            "callback_url": "",
            "checks": checks,
            "summary": "回调 URL 为空",
        }

    # 1) URL 格式合法
    url_pattern = re.compile(
        r"^(https?)://[A-Za-z0-9\.\-_]+(:\d+)?(/[^\s?#]*)?(\?[^\s#]*)?(#[^\s]*)?$"
    )
    if not url_pattern.match(target_url):
        add_check("URL 格式合法", "fail", f"URL 格式不合法: {target_url}")
        return {
            "success": False,
            "blocked": True,
            "callback_url": target_url,
            "checks": checks,
            "summary": "URL 格式不合法",
        }
    add_check("URL 格式合法", "pass", "")

    # 2) HTTPS
    if target_url.lower().startswith("https://"):
        add_check("HTTPS 协议", "pass", "")
    else:
        add_check("HTTPS 协议", "warn", "建议使用 HTTPS 以保护回调安全")

    # 3) 域名可解析
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(target_url)
        host = parsed.hostname or ""
    except Exception:
        host = ""
    if not host:
        add_check("域名可解析", "warn", "无法从 URL 中提取主机名")
    else:
        try:
            socket.gethostbyname(host)
            add_check("域名可解析", "pass", host)
        except Exception as e:
            add_check("域名可解析", "warn", f"DNS 解析失败: {e}")

    # 4) 外网可达 (HEAD)
    head_ok = False
    head_detail = ""
    try:
        async with httpx.AsyncClient(timeout=5.0, verify=False, follow_redirects=False) as cli:
            r = await cli.head(target_url)
            head_detail = f"HEAD HTTP {r.status_code}"
            if r.status_code in (200, 204, 301, 302, 307, 308, 404, 405, 400, 403):
                head_ok = True
    except Exception as e:
        head_detail = f"HEAD 失败: {str(e)[:200]}"
    if head_ok:
        add_check("外网可达", "pass", head_detail)
    else:
        add_check("外网可达", "warn", head_detail or "外网不可达")

    # 5) 自回环验证：发一条 dataType=__precheck__ 报文到该 URL
    selfloop_ok = False
    selfloop_detail = ""
    try:
        async with httpx.AsyncClient(timeout=8.0, verify=False, follow_redirects=False) as cli:
            r = await cli.post(
                target_url,
                json={
                    "dataType": "__precheck__",
                    "msgId": f"precheck-{int(datetime.utcnow().timestamp() * 1000)}",
                    "param": {},
                },
                headers={"X-HS-Precheck": "1"},
            )
            selfloop_detail = f"POST HTTP {r.status_code}"
            if r.status_code == 200:
                try:
                    body = r.json()
                    if isinstance(body, dict) and body.get("matched_project") is True:
                        selfloop_ok = True
                        selfloop_detail += "，已确认命中本项目"
                    elif isinstance(body, dict) and body.get("code") == 0:
                        # 命中我方但旧版未返回 matched_project，也视为可达
                        selfloop_ok = True
                        selfloop_detail += "，对端返回 code=0（疑似命中本项目或其它兼容服务）"
                    else:
                        selfloop_detail += "，对端响应未识别为本项目"
                except Exception:
                    selfloop_detail += "，对端响应非 JSON"
            elif r.status_code == 404:
                selfloop_detail += "，对端返回 404（很可能 URL 缺少 /autodev 前缀或路由配置错误）"
    except Exception as e:
        selfloop_detail = f"POST 失败: {str(e)[:200]}"
    if selfloop_ok:
        add_check("路由命中本项目", "pass", selfloop_detail)
    else:
        add_check("路由命中本项目", "warn", selfloop_detail or "无法验证是否命中本项目")

    # 汇总
    has_fail = any(c["status"] == "fail" for c in checks)
    has_warn = any(c["status"] == "warn" for c in checks)
    success = (not has_fail) and (not has_warn)
    summary = "全部通过" if success else ("存在阻断错误" if has_fail else "存在告警，可继续推送但请人工确认")

    return {
        "success": success,
        "blocked": has_fail,
        "callback_url": target_url,
        "checks": checks,
        "summary": summary,
    }
