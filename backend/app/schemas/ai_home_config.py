"""PRD-405 v1.0 AI 对话模式首页配置 Schemas。

v1.0 在 v0.5 基础上扩展为 6 Tab 结构：
- Tab1 欢迎区：主标题/副标题/头像图
- Tab2 首屏内容：今日健康贴士轮播 + 推荐问列表（双字段：显示文案 + 实际发送内容）+ 空对话占位
- Tab3 功能宫格：每项 7 字段（主文案/副说明/跳转/图标/渐变色/角标/启用）
- Tab4 输入栏：占位+语音+家庭成员胶囊+查看档案
- Tab5 会话策略：7 个全局对话策略字段
- Tab6 全局开关：9 个总开关 + 打卡按钮 4 字段

保留 v0.5 字段以兼容现有 H5 端，新增字段附在原结构上。
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ──────────────── Tab1：欢迎区 ────────────────


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
    # v1.0 新增：晓医风格主标题（支持 {昵称} 占位符）
    main_title: str = "早上好，{昵称}！"
    sub_title: str = "我是您的AI健康顾问小康"


# ──────────────── Tab2：首屏内容 ────────────────


class HealthTipsConfig(BaseModel):
    """今日健康贴士轮播（复用轮播图）。"""
    visible: bool = True
    interval_seconds: int = 4  # 3 ~ 5
    show_indicator: bool = True


class RecommendedQuestion(BaseModel):
    id: Optional[str] = None  # 新增时由后端自动生成
    # v1.0 改为双字段：显示文案 + 实际发送内容
    title: str = ""  # 显示文案（≤ 8 字）
    question: str = ""  # 实际发送内容（≤ 200 字）
    icon: str = "💡"  # Emoji 或图片 URL
    icon_image_url: Optional[str] = ""  # 图片版本
    enabled: bool = True
    sort: int = 0


class EmptyDialogPlaceholder(BaseModel):
    """空对话占位（精简版 2 字段）。"""
    icon: str = "💬"
    icon_image_url: Optional[str] = ""
    main_title: str = "还没有对话记录"


# ──────────────── Tab3：功能宫格 ────────────────


class FuncGridItem(BaseModel):
    """每个功能宫格项（v1.0 新增 7 字段结构）。"""
    id: Optional[str] = None
    main_text: str = ""  # 主文案（≤ 8 字）
    sub_text: str = ""  # 副说明（≤ 12 字）
    target_path: str = "/"  # 跳转链接
    icon: str = "📌"  # Emoji 或图片 URL
    icon_image_url: Optional[str] = ""
    gradient_start: str = "#5B6CFF"  # 起始色 HEX
    gradient_end: str = "#8B9AFF"  # 结束色 HEX
    badge: Optional[str] = ""  # 角标（≤ 4 字）
    enabled: bool = True
    sort: int = 0


# ──────────────── Tab4：输入栏 ────────────────


class FamilyConsultPill(BaseModel):
    """输入栏下方家庭成员咨询胶囊。"""
    enabled: bool = True
    template: str = "为({name})咨询"  # 必须含 {name} 占位符
    show_archive_link: bool = True
    archive_path: str = "/health-records"


class InputConfig(BaseModel):
    placeholder: str = "发消息或按住说话..."
    enable_voice: bool = True
    enable_tts: bool = True
    tts_provider: str = "auto"  # cloud / browser / auto
    # v1.0 新增：家庭成员咨询胶囊
    family_consult: FamilyConsultPill = Field(default_factory=FamilyConsultPill)


# ──────────────── Tab1：顶栏（保留 v0.5 字段） ────────────────


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
    # v1.0 设计图：删除整条顶栏（默认隐藏）
    visible: bool = False


# ──────────────── Tab5：会话策略（v1.0 新增 7 字段） ────────────────


class SessionStrategy(BaseModel):
    """全局对话策略（v1.0 新增 7 字段）。"""
    max_answer_chars: int = 1000  # 单次回答最大字数（100 ~ 5000）
    show_loading: bool = True  # AI 思考中加载动画
    daily_free_quota: int = 50  # 单日免费提问次数上限（1 ~ 999）
    answer_style: str = "friendly"  # 回答风格 professional/easy/friendly
    sensitive_filter: bool = True  # 敏感词过滤
    context_memory_rounds: int = 5  # 上下文记忆轮数 3/5/10/20
    disclaimer: str = "以上内容仅供参考，不能替代医生诊疗"  # 免责声明（≤ 100 字）


class EmptySessionWelcome(BaseModel):
    enabled: bool = False
    messages: List[str] = Field(default_factory=list)


class SessionConfig(BaseModel):
    idle_timeout_minutes: int = 30
    auto_new_session: bool = True
    empty_session_welcome: EmptySessionWelcome = Field(default_factory=EmptySessionWelcome)
    # v1.0 新增：会话策略
    strategy: SessionStrategy = Field(default_factory=SessionStrategy)


# ──────────────── Tab6：全局开关（v1.0 新增 9 个总开关） ────────────────


class GlobalSwitches(BaseModel):
    """模块级总开关（9 个）。"""
    welcome_visible: bool = True  # 1. 欢迎区整块显隐
    health_tips_visible: bool = True  # 2. 今日健康贴士整块显隐
    func_grid_visible: bool = True  # 3. 功能宫格整块显隐
    recommended_visible: bool = True  # 4. 推荐问整块显隐
    empty_placeholder_visible: bool = True  # 5. 空对话占位整块显隐
    family_pill_visible: bool = True  # 6. 输入栏家庭成员咨询胶囊
    archive_link_visible: bool = True  # 7. 输入栏查看档案按钮
    voice_input_visible: bool = True  # 8. 输入栏语音输入图标
    floating_button_visible: bool = True  # 9. 打卡悬浮按钮整块


class BannerVisible(BaseModel):
    visible: bool = True


class FuncGridConfig(BaseModel):
    """v1.0 重构：将原 visible/columns/max_count 与 items 合一。

    [AICHAT-OPTIM-FIX-V1 F-03 2026-05-14] 增加 `cols` 字段（与 columns 同义），
    供 admin 简化面板使用；items 字段标记 deprecated（保留兼容老数据，但 H5 不再读取）。
    """
    visible: bool = True
    columns: int = 3
    # [AICHAT-OPTIM-FIX-V1 F-03] 与 columns 同义，新简化面板使用 cols 字段名
    cols: Optional[int] = None
    max_count: int = 6
    # v1.0 新增：宫格项详细配置（默认 3 项：AI诊室/看报告/健康档案）
    items: List[FuncGridItem] = Field(
        default_factory=lambda: [
            FuncGridItem(
                id="g1", main_text="AI诊室", sub_text="智能问诊", target_path="/ai-doctor",
                icon="🩺", gradient_start="#5B6CFF", gradient_end="#8B9AFF", sort=1,
            ),
            FuncGridItem(
                id="g2", main_text="看报告", sub_text="解读体检报告", target_path="/checkup",
                icon="📋", gradient_start="#FF7E5F", gradient_end="#FEB47B", sort=2,
            ),
            FuncGridItem(
                id="g3", main_text="健康档案", sub_text="查看个人档案", target_path="/health-archive",
                icon="📁", gradient_start="#43E97B", gradient_end="#38F9D7", sort=3,
            ),
        ]
    )


class QuickTagsConfig(BaseModel):
    visible: bool = True
    max_count: int = 8


class FloatingButtonConfig(BaseModel):
    enabled: bool = True
    icon: str = "✅"
    icon_image_url: Optional[str] = ""
    label: Optional[str] = "健康打卡"
    show_label: bool = True  # v1.0 默认显示文案
    target_path: str = "/health-plan"
    position: str = "right_bottom"  # right_bottom / left_bottom（v1.0 固定右下，但保留兼容）


# ──────────────── PRD-414 v1.1：AI 对话页（chat 页）配置 ────────────────


class AIChatAvatar(BaseModel):
    """AI 对话头像（PRD-414 §3.7）。
    与系统/品牌 Logo 完全解耦，单独维护。
    """
    type: str = "emoji"  # emoji / image
    emoji: Optional[str] = "🌿"  # emoji 兜底
    image_url: Optional[str] = ""  # 推荐 128x128 PNG/JPG/WEBP，≤500KB


class AIChatConfig(BaseModel):
    """AI 对话页（chat）配置 v1.1。
    覆盖 PRD-414 中"AI 头像 / 署名 / 档案行 / 健康打卡可拖动 / 回到最新消息"等能力开关。
    """
    avatar: AIChatAvatar = Field(default_factory=AIChatAvatar)
    signature: str = "小康"  # AI 署名（默认"小康"，14px 主文本色）
    profile_row_enabled: bool = True  # 档案行总开关（PRD-414 §3.4）
    profile_row_template: str = "本次回答结合 {name} 的档案"  # 档案行文案模板，{name} 占位符
    punchcard_draggable: bool = True  # 健康打卡是否可拖动（PRD-414 §3.2）
    scroll_to_bottom_button: bool = True  # 是否显示"回到最新消息"按钮（PRD-414 §3.1）
    sticky_topbar: bool = True  # 顶栏是否吸顶（PRD-414 §3.1）
    history_retention_days: int = 0  # 历史会话保留天数；0=永久（PRD-414 O-04）


# ──────────────── 总配置 ────────────────


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
    recommended_questions: List[RecommendedQuestion] = Field(
        default_factory=lambda: [
            RecommendedQuestion(id="r1", title="体检解读", question="帮我解读最新体检报告", icon="📋", sort=1),
            RecommendedQuestion(id="r2", title="用药咨询", question="感冒了吃什么药比较好？", icon="💊", sort=2),
            RecommendedQuestion(id="r3", title="饮食建议", question="高血压患者饮食注意什么？", icon="🥗", sort=3),
        ]
    )
    # v1.0 新增模块
    health_tips: HealthTipsConfig = Field(default_factory=HealthTipsConfig)
    empty_placeholder: EmptyDialogPlaceholder = Field(default_factory=EmptyDialogPlaceholder)
    global_switches: GlobalSwitches = Field(default_factory=GlobalSwitches)
    # v1.1 PRD-414 新增：AI 对话页配置
    ai_chat: AIChatConfig = Field(default_factory=AIChatConfig)


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
