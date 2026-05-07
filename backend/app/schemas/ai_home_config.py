"""PRD-405 AI 对话模式首页配置 Schemas。"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class WelcomeAvatar(BaseModel):
    type: str = "emoji"  # emoji / image
    emoji: Optional[str] = "🌿"
    image_url: Optional[str] = ""


class WelcomeGreetings(BaseModel):
    morning: List[str] = Field(default_factory=lambda: ["早上好"])
    afternoon: List[str] = Field(default_factory=lambda: ["午安"])
    evening: List[str] = Field(default_factory=lambda: ["晚上好"])


class WelcomeConfig(BaseModel):
    avatar: WelcomeAvatar = Field(default_factory=WelcomeAvatar)
    greetings: WelcomeGreetings = Field(default_factory=WelcomeGreetings)
    subtitles: List[str] = Field(default_factory=lambda: ["有什么健康问题想问我?"])
    show_nickname: bool = True


class TopbarLogo(BaseModel):
    type: str = "emoji"
    emoji: Optional[str] = "🌿"
    image_url: Optional[str] = ""


class TopbarConfig(BaseModel):
    title: str = "AI 健康助手"
    logo: TopbarLogo = Field(default_factory=TopbarLogo)
    show_sidebar: bool = True
    show_more_menu: bool = True
    show_share: bool = True


class RecommendedQuestion(BaseModel):
    id: Optional[str] = None  # 新增时由后端自动生成
    icon: str = "💡"
    title: str = ""
    question: str = ""
    enabled: bool = True
    sort: int = 0


class FloatingButtonConfig(BaseModel):
    enabled: bool = True
    icon: str = "✅"
    label: Optional[str] = "健康打卡"
    show_label: bool = False
    target_path: str = "/health-check-in"
    position: str = "right_bottom"  # right_bottom / left_bottom


class InputConfig(BaseModel):
    placeholder: str = "问问健康助手..."
    enable_voice: bool = True
    enable_tts: bool = True
    tts_provider: str = "auto"  # cloud / browser / auto


class EmptySessionWelcome(BaseModel):
    enabled: bool = False
    messages: List[str] = Field(default_factory=list)


class SessionConfig(BaseModel):
    idle_timeout_minutes: int = 30
    auto_new_session: bool = True
    empty_session_welcome: EmptySessionWelcome = Field(default_factory=EmptySessionWelcome)


class BannerVisible(BaseModel):
    visible: bool = True


class FuncGridConfig(BaseModel):
    visible: bool = True
    columns: int = 3
    max_count: int = 6


class QuickTagsConfig(BaseModel):
    visible: bool = True
    max_count: int = 8


class AIHomeConfigPayload(BaseModel):
    """完整配置 JSON。"""

    welcome: WelcomeConfig = Field(default_factory=WelcomeConfig)
    topbar: TopbarConfig = Field(default_factory=TopbarConfig)
    input: InputConfig = Field(default_factory=InputConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    floating_button: FloatingButtonConfig = Field(default_factory=FloatingButtonConfig)
    banner: BannerVisible = Field(default_factory=BannerVisible)
    func_grid: FuncGridConfig = Field(default_factory=FuncGridConfig)
    quick_tags: QuickTagsConfig = Field(default_factory=QuickTagsConfig)
    recommended_questions: List[RecommendedQuestion] = Field(default_factory=list)


class AIHomeConfigResponse(BaseModel):
    config: AIHomeConfigPayload
    updated_at: Optional[datetime] = None


class AIHomeModulePatch(BaseModel):
    """按模块局部保存。"""

    data: Any


# ── 操作日志 ──


class AIHomeConfigLogItem(BaseModel):
    id: int
    operator_id: Optional[int] = None
    operator_name: Optional[str] = None
    module: str
    summary: Optional[str] = None
    operator_ip: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AIHomeConfigLogDetail(AIHomeConfigLogItem):
    before_json: Optional[Any] = None
    after_json: Optional[Any] = None


class AIHomeConfigLogList(BaseModel):
    items: List[AIHomeConfigLogItem]
    total: int
