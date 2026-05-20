"""[PRD-AICHAT-FUNCCARD-V2 2026-05-20] AI 对话页「功能引导卡片」新版样式改造 - 前端源码校验测试

本次需求是 H5 端 + admin-web 端纯 UI 改造（不涉及后端 DB / API 变更），
因此本测试通过校验前端源码文件的关键字符串/正则，确保改造已落地、不被回滚。

覆盖（共 11 个用例）：
- TC-01：h5-web 新建 FunctionCardV2.tsx 文件存在且导出默认组件
- TC-02：FunctionCardV2.tsx 视觉规范 token 落地（白底 / 1px #E0F2FE 描边 / 16 圆角 / shadow）
- TC-03：FunctionCardV2.tsx 主标题 18px 600 + 副标题 13px + 按钮副说明 12px #94A3B8
- TC-04：FunctionCardV2.tsx 主按钮高 44 / 圆角 22 / 渐变 #38BDF8→#0284C7 / 白字 16 600
- TC-05：ChatCards.tsx 引入 FunctionCardV2 并在 NavigateCard / SdkCallCard / UploadCard 中使用
- TC-06：QuestionnairePreCard.tsx 完全委托 FunctionCardV2 渲染（一刀切刷新，无版本字段判断）
- TC-07：ai-home/page.tsx 把 button_sub_desc 透传到 questionnairePreCard.buttonSubDesc
- TC-08：admin-web 新建 FunctionCardV2Preview.tsx 且包含 PhonePreviewFrame 375x667
- TC-09：admin-web function-buttons/page.tsx 引入 FunctionCardV2Preview + 预览触发按钮
- TC-10：function-buttons/page.tsx 预览 Modal 实时绑定表单字段（Form.useWatch）
- TC-11：FunctionCardV2 渲染整卡可点击（onClick 容器级 + 主按钮 stopPropagation 防双触发）

测试在「项目根目录可读取到 h5-web / admin-web 源码」时执行。若运行环境无对应目录，
本测试整文件 skip，避免误报。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# ────────────────────────────── 路径解析 ──────────────────────────────
_HERE = Path(__file__).resolve()
_CANDIDATES = [
    _HERE.parents[2],  # 本地：<repo_root>
    _HERE.parents[1],  # 容器：/app（部署脚本会 docker cp h5-web/admin-web 源到 /app/）
]


def _resolve_files():
    for root in _CANDIDATES:
        fcv2 = root / "h5-web" / "src" / "components" / "ai-chat" / "FunctionCardV2.tsx"
        cc = root / "h5-web" / "src" / "components" / "ai-chat" / "ChatCards.tsx"
        qpc = root / "h5-web" / "src" / "components" / "ai-chat" / "QuestionnairePreCard.tsx"
        ai_home = root / "h5-web" / "src" / "app" / "(ai-chat)" / "ai-home" / "page.tsx"
        fcv2_preview = root / "admin-web" / "src" / "components" / "FunctionCardV2Preview.tsx"
        fb_page = root / "admin-web" / "src" / "app" / "(admin)" / "function-buttons" / "page.tsx"
        if all(p.exists() for p in [fcv2, cc, qpc, ai_home, fcv2_preview, fb_page]):
            return fcv2, cc, qpc, ai_home, fcv2_preview, fb_page
    return None, None, None, None, None, None


FCV2, CHATCARDS, QPC, AI_HOME, FCV2_PREVIEW, FB_PAGE = _resolve_files()

pytestmark = pytest.mark.skipif(
    any(p is None for p in [FCV2, CHATCARDS, QPC, AI_HOME, FCV2_PREVIEW, FB_PAGE]),
    reason="frontend source not available in current environment",
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ─────────────────── TC-01 ───────────────────


def test_tc01_fcv2_component_exists_and_default_export():
    """新建 FunctionCardV2.tsx 文件存在且导出默认组件。"""
    src = _read(FCV2)
    assert "export default function FunctionCardV2" in src, "FunctionCardV2 默认导出未找到"
    assert "export interface FunctionCardV2Data" in src, "FunctionCardV2Data 接口未导出"


# ─────────────────── TC-02 ───────────────────


def test_tc02_card_container_visual_tokens():
    """卡片容器：白底 + #E0F2FE 描边 + 16 圆角 + 蓝色阴影 token 全部落地。"""
    src = _read(FCV2)
    assert "#FFFFFF" in src, "卡片白底 #FFFFFF 未找到"
    assert "#E0F2FE" in src, "卡片描边色 #E0F2FE 未找到"
    assert "borderRadius: 16" in src, "16px 圆角未找到"
    assert "rgba(2, 132, 199, 0.10)" in src, "卡片蓝色阴影 token 未找到"


# ─────────────────── TC-03 ───────────────────


def test_tc03_typography_tokens():
    """主标题 18 / 600 + 副标题 13 / #64748B + 按钮副说明 12 / #94A3B8 token 全部落地。"""
    src = _read(FCV2)
    assert "fontSize: 18" in src and "fontWeight: 600" in src and "#0F172A" in src, "主标题 token 缺失"
    assert "fontSize: 13" in src and "#64748B" in src, "副标题 token 缺失"
    assert "fontSize: 12" in src and "#94A3B8" in src, "按钮副说明 token 缺失"


# ─────────────────── TC-04 ───────────────────


def test_tc04_primary_button_tokens():
    """主按钮高 44 / 圆角 22 / 渐变 #38BDF8→#0284C7 / 白字 16 600。"""
    src = _read(FCV2)
    assert "height: 44" in src, "按钮高度 44 未找到"
    assert "borderRadius: 22" in src, "按钮圆角 22 未找到"
    assert "#38BDF8" in src and "#0284C7" in src, "按钮渐变色未找到"
    assert "linear-gradient(135deg, #38BDF8 0%, #0284C7 100%)" in src, "按钮渐变完整声明缺失"


# ─────────────────── TC-05 ───────────────────


def test_tc05_chatcards_uses_fcv2():
    """ChatCards.tsx 引入 FunctionCardV2 并在 Navigate / SdkCall / Upload 卡片中使用。"""
    src = _read(CHATCARDS)
    assert "from './FunctionCardV2'" in src, "ChatCards 未引入 FunctionCardV2"
    assert "import FunctionCardV2" in src, "FunctionCardV2 import 缺失"
    # 三个卡片函数体内必须出现 FunctionCardV2 标签
    for fn_name in ["function NavigateCard", "function SdkCallCard", "function UploadCard"]:
        idx = src.find(fn_name)
        assert idx > 0, f"{fn_name} 未找到"
        # 取 fn 之后 1200 字符内必须出现 <FunctionCardV2
        snippet = src[idx : idx + 1500]
        assert "<FunctionCardV2" in snippet, f"{fn_name} 未使用 FunctionCardV2 渲染"


# ─────────────────── TC-06 ───────────────────


def test_tc06_questionnaire_pre_card_delegates_to_fcv2():
    """QuestionnairePreCard 完全委托 FunctionCardV2 渲染。"""
    src = _read(QPC)
    assert "import FunctionCardV2" in src, "QuestionnairePreCard 未引入 FunctionCardV2"
    assert "<FunctionCardV2" in src, "QuestionnairePreCard 未使用 FunctionCardV2"
    # 一刀切刷新：不允许出现版本字段判断
    assert "version" not in src.lower() or "// no version" in src.lower(), (
        "QuestionnairePreCard 不应出现版本字段判断（一刀切刷新原则）"
    )


# ─────────────────── TC-07 ───────────────────


def test_tc07_ai_home_passes_button_sub_desc_to_pre_card():
    """ai-home/page.tsx 把 button_sub_desc 透传到 questionnairePreCard.buttonSubDesc。"""
    src = _read(AI_HOME)
    # 数据组装段
    assert "buttonSubDesc" in src, "ai-home 未透传 buttonSubDesc"
    assert "btnSubDescText" in src or "button_sub_desc" in src, "ai-home 未从后端 button_sub_desc 取值"
    # 类型定义中也要加 buttonSubDesc 字段
    m = re.search(r"questionnairePreCard\?:\s*\{[^}]*buttonSubDesc", src, re.S)
    assert m, "ChatMessage.questionnairePreCard 类型未加 buttonSubDesc 字段"


# ─────────────────── TC-08 ───────────────────


def test_tc08_admin_preview_component_with_phone_frame():
    """admin-web 新建 FunctionCardV2Preview 且包含 PhonePreviewFrame 375x667。"""
    src = _read(FCV2_PREVIEW)
    assert "export default function FunctionCardV2Preview" in src, "FunctionCardV2Preview 默认导出缺失"
    assert "export function PhonePreviewFrame" in src, "PhonePreviewFrame 命名导出缺失"
    # 手机框 375 x 667
    assert "width: 375" in src, "PhonePreviewFrame 宽度 375 未找到"
    assert "height: 667" in src, "PhonePreviewFrame 高度 667 未找到"
    # token 与 H5 端保持一致
    assert "#E0F2FE" in src and "#38BDF8" in src and "#0284C7" in src, "预览组件视觉 token 与 H5 不一致"


# ─────────────────── TC-09 ───────────────────


def test_tc09_admin_function_buttons_page_has_preview_trigger():
    """function-buttons/page.tsx 引入预览组件 + 触发按钮 + 预览 Modal。"""
    src = _read(FB_PAGE)
    assert "FunctionCardV2Preview" in src, "未引入 FunctionCardV2Preview"
    assert "PhonePreviewFrame" in src, "未引入 PhonePreviewFrame"
    assert "previewOpen" in src and "setPreviewOpen" in src, "预览浮层 state 未声明"
    assert 'data-testid="function-card-preview-trigger"' in src, "预览触发按钮 testid 未设置"
    assert "预览效果" in src, "预览触发按钮文案未找到"


# ─────────────────── TC-10 ───────────────────


def test_tc10_admin_preview_modal_binds_form_fields_live():
    """预览 Modal 内部数据来源于 Form.useWatch 实时联动，无需保存。"""
    src = _read(FB_PAGE)
    for field in [
        "watchedCardTitle",
        "watchedCardSubtitle",
        "watchedButtonSubDesc",
        "watchedPreCardIcon",
        "watchedPreCardIconType",
    ]:
        assert field in src, f"预览实时联动字段 {field} 缺失"
    # 必须把这些字段透传给 FunctionCardV2Preview
    m = re.search(r"<FunctionCardV2Preview[\s\S]*?data=\{\{([\s\S]*?)\}\}", src)
    assert m, "FunctionCardV2Preview 未传入 data prop"
    block = m.group(1)
    assert "watchedCardTitle" in block, "预览未绑定 watchedCardTitle"
    assert "watchedButtonSubDesc" in block, "预览未绑定 watchedButtonSubDesc"


# ─────────────────── TC-11 ───────────────────


def test_tc11_card_whole_clickable_with_stop_propagation():
    """整卡可点击：容器 onClick + 主按钮 stopPropagation 防双触发。"""
    src = _read(FCV2)
    assert "onClick={handleCardClick}" in src, "卡片容器未绑定整卡 onClick"
    assert "e.stopPropagation()" in src, "主按钮未 stopPropagation 防双触发"
    # 防误触：点击落在 [data-fcv2-stop="1"] 元素上不冒泡
    assert "data-fcv2-stop" in src, "未设置 data-fcv2-stop 防冒泡标记"
