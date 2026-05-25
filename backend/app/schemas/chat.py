from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_serializer


# [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517] 通用聊天 intent 枚举：
# - report_interpret：报告解读（OCR + 报告专属 prompt）
# - drug_identify   ：拍照识药（保留兼容）
# - health_qa       ：通用健康咨询（占位）
# 其他客户端不传 intent 时行为与历史完全一致。
class ChatIntent(str, Enum):
    REPORT_INTERPRET = "report_interpret"
    DRUG_IDENTIFY = "drug_identify"
    HEALTH_QA = "health_qa"


def _to_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    """[BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517]
    把数据库里 naive UTC 的 datetime 序列化为带 UTC 时区标识的 ISO 字符串，
    避免前端按本地时区误解析（"刚发生"显示为"8 小时前"）。
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


class ChatSessionCreate(BaseModel):
    # [Bug-419 2026-05-08] session_type 改为可选并提供默认值兜底，避免任何客户端
    # 字段疏漏导致 422 必现。后端在路由层会进一步校验合法枚举值，非法值兜底为 health_qa。
    session_type: Optional[str] = "health_qa"
    title: Optional[str] = None
    family_member_id: Optional[int] = None
    symptom_info: Optional[dict] = None
    # [Bug-419 兼容字段] H5 早期实现误将 family_member_id 写为 member_id，此处显式
    # 接收旧字段并在路由层归一化为 family_member_id，避免老客户端版本继续 422。
    member_id: Optional[int] = None


class ChatSessionResponse(BaseModel):
    id: int
    user_id: int
    session_type: str
    title: Optional[str] = None
    family_member_id: Optional[int] = None
    symptom_info: Optional[dict] = None
    # [PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] 会话状态相关字段
    status: Optional[str] = "archived"
    archived_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    message_count: Optional[int] = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    # [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517] 时区规范
    @field_serializer("created_at", "updated_at", "archived_at", "last_active_at")
    def _ser_dt(self, v: Optional[datetime], _info):
        return _to_utc_iso(v)


class ChatMessageCreate(BaseModel):
    content: str
    message_type: str = "text"
    file_url: Optional[str] = None
    silent: Optional[bool] = False
    # [Bug-433 2026-05-09] 用户消息来源入口：text / voice / preset / voice_repair
    # 默认 text，便于在 chat_messages 表中区分会话首句的实际来源（文字/语音/预设按钮），
    # 用于排查"语音/预设按钮首句丢失"类回归与运营分析。非法值在路由层归一化为 'text'。
    source: Optional[str] = "text"
    # [BUG_FIX_拍照识药三联_20260516] 方案 E 新增字段：
    # - button_type：拍照识药 / 健康自查 / 报告解读等按钮入口类型；
    #   后端据此把消息路由到聊天内嵌识药引擎或其他专用流程。
    # - family_member_id：当前咨询人 ID（妈妈给孩子拍药时务必传入孩子的 ID）；
    #   决定档案上下文（剂量/禁忌/相互作用）来源，避免给儿童按成人剂量。
    button_type: Optional[str] = None
    family_member_id: Optional[int] = None
    # [BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517] 通用意图协议（向后兼容）：
    # - intent      : 显式声明本次消息意图，最高优先级；支持值见 ChatIntent
    # - image_urls  : 图片 URL 数组（与历史 content 内嵌 URL 兼容；优先此字段）
    # - button_id   : 功能按钮 ID（来自 chat_function_buttons 表），用于路由命中
    # - report_meta : 报告解读专属可选结构化上下文（标题/日期）
    intent: Optional[str] = None
    image_urls: Optional[List[str]] = None
    button_id: Optional[int] = None
    report_meta: Optional[dict] = None
    # [BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525]
    # 后台「功能按钮管理」3 层配置体系新增透传字段：
    # - ai_function_type：button_type=ai_function 时的子类型
    #   (questionnaire / image_capture / file_upload / ai_dialog_trigger / quick_ask
    #    及老兼容 photo_upload / report_interpret / medicine_recognize / check)
    # - capture_purpose：ai_function_type=image_capture 时的图像采集子用途
    #   (identify_medicine / upload / interpret_report)
    # 后端 resolve_button_intent 据此把任意配置统一路由到专用引擎。
    ai_function_type: Optional[str] = None
    capture_purpose: Optional[str] = None


class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    message_type: str
    file_url: Optional[str] = None
    created_at: datetime
    # [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517 · Bug-3]
    # 把识药卡片元数据回吐给前端，刷新 / 跨设备 时能还原"已加入用药计划"等状态。
    message_metadata: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)

    # [BUG_FIX_AI_HOME_DRUG_IDENTIFY_OPTIM_20260517] 时区规范
    @field_serializer("created_at")
    def _ser_dt(self, v: Optional[datetime], _info):
        return _to_utc_iso(v)


class AIQueryRequest(BaseModel):
    content: str
    session_type: str = "health_qa"
    session_id: Optional[int] = None
    family_member_id: Optional[int] = None
