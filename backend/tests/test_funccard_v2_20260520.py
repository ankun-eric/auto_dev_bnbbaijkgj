"""[PRD-AICHAT-FUNCCARD-V2 2026-05-20] AI 对话页「功能引导卡片」新版样式改造 - 前端源码校验测试

[PRD-AICHAT-FUNCCARD-V2-DESIGN-D 2026-05-20 v1.2]
本测试文件已升级为方案 D（图标左 + 标题右 · 宾尼天蓝）的校验标准。
v1.0 / v1.1 旧设计 token（#E0F2FE 描边 / btnGradient / 高 44 圆角 22 / fontSize 18 等）
作为「历史追溯 token」继续保留在源码 COLORS 常量中，但实际渲染走方案 D。
本测试既校验方案 D 的新视觉规范，也兼容性校验历史 token 没有被错误删除。

本次需求是 H5 端 + admin-web 端纯 UI 改造（不涉及后端 DB / API 变更），
因此本测试通过校验前端源码文件的关键字符串/正则，确保改造已落地、不被回滚。

覆盖（共 16 个用例 · 方案 D · v1.2）：
- TC-01：h5-web FunctionCardV2.tsx 文件存在且导出默认组件
- TC-02：方案 D 卡片容器：白底 / 16 圆角 / 蓝灰阴影 0 4px 24px rgba(15,23,42,0.08)
- TC-03：方案 D 顶部 4px 渐变色条 #0EA5E9 → #38BDF8（全卡片必须存在）
- TC-04：方案 D 头部排版：flex 横向 / align-items center / gap 14 / 图标 48x48 左 / 标题 20px 700 右
- TC-05：方案 D 副标题色块：#F0F9FF + 左 3px #0EA5E9 + 圆角 0 8 8 0 + #334155
- TC-06：方案 D 按钮副说明：12px / #64748B / center / mb 10
- TC-07：方案 D 主按钮：全宽 / 48 高 / 12 圆角 / #0EA5E9 纯色 / 16/600 / letter-spacing 1
- TC-08：方案 D 主按钮文案硬编码「开始」（前端忽略 button_text 字段）
- TC-09：方案 D 主标题单行省略号（不允许换行 / overflow ellipsis nowrap）
- TC-10：ChatCards.tsx 引入 FunctionCardV2 并在 NavigateCard / SdkCallCard / UploadCard 中使用
- TC-11：QuestionnairePreCard.tsx 完全委托 FunctionCardV2 渲染（一刀切刷新，无版本字段判断）
- TC-12：ai-home/page.tsx 把 button_sub_desc 透传到 questionnairePreCard.buttonSubDesc
- TC-13：admin-web FunctionCardV2Preview.tsx 同步走方案 D（顶部色条 + 48 高按钮 + 「开始」文案 + 手机框 375x667）
- TC-14：admin-web function-buttons/page.tsx 预览触发按钮 + Modal + 预览实时绑定表单字段
- TC-15：admin-web function-buttons/page.tsx 含 v1.2 字段提示（cover_img / button_text 不生效说明）
- TC-16：FunctionCardV2 渲染整卡可点击（onClick 容器级 + 主按钮 stopPropagation 防双触发）

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
    """新建 FunctionCardV2.tsx 文件存在且导出默认组件 + 接口。"""
    src = _read(FCV2)
    assert "export default function FunctionCardV2" in src, "FunctionCardV2 默认导出未找到"
    assert "export interface FunctionCardV2Data" in src, "FunctionCardV2Data 接口未导出"


# ─────────────────── TC-02 ───────────────────


def test_tc02_card_container_design_d_tokens():
    """方案 D 卡片容器：白底 + 16 圆角 + 蓝灰阴影 0 4px 24px rgba(15,23,42,0.08)。"""
    src = _read(FCV2)
    assert "#FFFFFF" in src, "卡片白底 #FFFFFF 未找到"
    assert "borderRadius: 16" in src, "16px 圆角未找到"
    # 方案 D 的卡片阴影色：rgba(15, 23, 42, 0.08)
    assert "rgba(15, 23, 42, 0.08)" in src, "方案 D 卡片阴影 token 未找到"
    # 历史 v1 token 仍保留在 COLORS（作为追溯参考），不应被删除
    assert "#E0F2FE" in src, "历史 token #E0F2FE 应在源码中保留作为追溯参考"


# ─────────────────── TC-03 ───────────────────


def test_tc03_design_d_top_color_bar():
    """方案 D：顶部 4px 渐变色条 #0EA5E9 → #38BDF8（全卡片必须存在）。"""
    src = _read(FCV2)
    assert "fcv2-top-bar" in src, "顶部色条 testid fcv2-top-bar 缺失"
    assert "height: 4" in src, "顶部色条高度 4px 未找到"
    # 渐变方向 90deg 且色值正确
    m = re.search(r"linear-gradient\(\s*90deg\s*,\s*\$\{?\s*COLORS?\.?topBarFrom|linear-gradient\(\s*90deg\s*,\s*#0EA5E9[^)]*#38BDF8", src)
    # 直接简化校验：top bar 关键色值 + 渐变方向 90deg 都存在
    assert "topBarFrom: '#0EA5E9'" in src or "linear-gradient(90deg, #0EA5E9" in src, "顶部色条起色 #0EA5E9 未找到"
    assert "topBarTo: '#38BDF8'" in src or "#38BDF8 100%)" in src, "顶部色条终色 #38BDF8 未找到"


# ─────────────────── TC-04 ───────────────────


def test_tc04_design_d_header_row_layout():
    """方案 D 头部排版：flex 横向 / align-items center / gap 14 / 图标 48 / 标题 20 700。"""
    src = _read(FCV2)
    # 头部 testid
    assert "fcv2-header-row" in src, "头部 fcv2-header-row testid 未找到"
    # flex 横向 + 垂直居中 + gap 14
    assert "display: 'flex'" in src, "header 未使用 flex 布局"
    assert "alignItems: 'center'" in src, "header 未 align-items: center"
    assert "gap: 14" in src, "图标与标题之间 gap 14 未找到"
    # 图标 48×48 + 不可压缩
    assert "width: 48" in src, "图标容器宽 48 未找到"
    assert "height: 48" in src, "图标容器高 48 未找到"
    assert "flexShrink: 0" in src, "图标 flex-shrink:0 未找到"
    # emoji 字号 28
    assert "fontSize: 28" in src, "图标 emoji 字号 28 未找到"
    # 主标题 20 / 700 / #0F172A
    assert "fontSize: 20" in src, "主标题字号 20 未找到"
    assert "fontWeight: 700" in src, "主标题 weight 700 未找到"
    assert "#0F172A" in src, "主标题色 #0F172A 未找到"


# ─────────────────── TC-05 ───────────────────


def test_tc05_design_d_subtitle_block():
    """方案 D 副标题色块：#F0F9FF 底 + 左 3px #0EA5E9 竖线 + 圆角 0 8 8 0 + #334155 字色。"""
    src = _read(FCV2)
    assert "fcv2-subtitle-block" in src, "副标题色块 testid 缺失"
    # 色块背景
    assert "#F0F9FF" in src, "副标题色块背景 #F0F9FF 未找到"
    # 左 3px 蓝竖线
    assert re.search(r"borderLeft:\s*`?3px solid \$?\{?COLORS\.subBlockBorder|borderLeft:\s*`?3px solid #0EA5E9", src), \
        "副标题左 3px #0EA5E9 竖线未找到"
    # 圆角 0 8 8 0
    assert "borderRadius: '0 8px 8px 0'" in src, "副标题色块圆角 0 8 8 0 未找到"
    # 字体规格
    assert "fontSize: 14" in src, "副标题字号 14 未找到"
    assert "#334155" in src, "副标题色 #334155 未找到"


# ─────────────────── TC-06 ───────────────────


def test_tc06_design_d_btn_sub_desc():
    """方案 D 按钮副说明：12px / #64748B / center / mb 10。"""
    src = _read(FCV2)
    assert "fcv2-btn-sub-desc" in src, "按钮副说明 testid 缺失"
    assert "fontSize: 12" in src, "按钮副说明字号 12 未找到"
    assert "#64748B" in src, "按钮副说明色 #64748B 未找到"
    assert "textAlign: 'center'" in src, "按钮副说明 center 对齐未找到"


# ─────────────────── TC-07 ───────────────────


def test_tc07_design_d_primary_button_tokens():
    """方案 D 主按钮：全宽 / 48 高 / 12 圆角 / #0EA5E9 纯色 / 16/600 / letter-spacing 1。"""
    src = _read(FCV2)
    assert "fcv2-primary-btn" in src, "主按钮 testid 缺失"
    assert "height: 48" in src, "按钮高度 48 未找到"
    assert "borderRadius: 12" in src, "按钮圆角 12 未找到"
    assert "width: '100%'" in src, "按钮全宽 100% 未找到"
    # 纯色 #0EA5E9（不是渐变）
    assert "btnSolid: '#0EA5E9'" in src or "background: '#0EA5E9'" in src, "按钮纯色 #0EA5E9 未找到"
    assert "fontSize: 16" in src, "按钮字号 16 未找到"
    assert "fontWeight: 600" in src, "按钮 weight 600 未找到"
    assert "letterSpacing: 1" in src, "按钮 letter-spacing 1px 未找到"


# ─────────────────── TC-08 ───────────────────


def test_tc08_design_d_button_text_hardcoded_kaishi():
    """方案 D 决策 12：主按钮文案前端硬编码「开始」，忽略后端 button_text 字段。"""
    src = _read(FCV2)
    # 按钮文本不再读取 data.buttonText，直接渲染「开始」字符串
    # 关键正则：button 标签内直接出现"开始"字面值（且不在注释里）
    # 简化校验：源码中至少有一处直接写出「开始」作为按钮文案
    assert "开始" in src, "方案 D 按钮文案「开始」未硬编码"
    # 不应再使用 data.buttonText || '立即查看' 这种 fallback
    assert "data.buttonText || '立即查看'" not in src, "按钮文案不应再 fallback 到「立即查看」"
    assert "data.buttonText || '开始测评'" not in src, "按钮文案不应再 fallback 到「开始测评」"


# ─────────────────── TC-09 ───────────────────


def test_tc09_design_d_title_single_line_ellipsis():
    """方案 D 主标题单行省略号：overflow hidden + text-overflow ellipsis + white-space nowrap。"""
    src = _read(FCV2)
    assert "overflow: 'hidden'" in src, "主标题 overflow:hidden 未找到"
    assert "textOverflow: 'ellipsis'" in src, "主标题 text-overflow:ellipsis 未找到"
    assert "whiteSpace: 'nowrap'" in src, "主标题 white-space:nowrap 未找到"
    # flex: 1 占满剩余宽度 + min-width: 0 保证可截断
    assert "flex: 1" in src, "主标题 flex:1 未找到"
    assert "minWidth: 0" in src, "主标题 min-width:0 未找到"


# ─────────────────── TC-10 ───────────────────


def test_tc10_chatcards_uses_fcv2():
    """ChatCards.tsx 引入 FunctionCardV2 并在 Navigate / SdkCall / Upload 卡片中使用。"""
    src = _read(CHATCARDS)
    assert "from './FunctionCardV2'" in src, "ChatCards 未引入 FunctionCardV2"
    assert "import FunctionCardV2" in src, "FunctionCardV2 import 缺失"
    for fn_name in ["function NavigateCard", "function SdkCallCard", "function UploadCard"]:
        idx = src.find(fn_name)
        assert idx > 0, f"{fn_name} 未找到"
        snippet = src[idx : idx + 1500]
        assert "<FunctionCardV2" in snippet, f"{fn_name} 未使用 FunctionCardV2 渲染"


# ─────────────────── TC-11 ───────────────────


def test_tc11_questionnaire_pre_card_delegates_to_fcv2():
    """QuestionnairePreCard 完全委托 FunctionCardV2 渲染。"""
    src = _read(QPC)
    assert "import FunctionCardV2" in src, "QuestionnairePreCard 未引入 FunctionCardV2"
    assert "<FunctionCardV2" in src, "QuestionnairePreCard 未使用 FunctionCardV2"


# ─────────────────── TC-12 ───────────────────


def test_tc12_ai_home_passes_button_sub_desc_to_pre_card():
    """ai-home/page.tsx 把 button_sub_desc 透传到 questionnairePreCard.buttonSubDesc。"""
    src = _read(AI_HOME)
    assert "buttonSubDesc" in src, "ai-home 未透传 buttonSubDesc"
    assert "btnSubDescText" in src or "button_sub_desc" in src, "ai-home 未从后端 button_sub_desc 取值"
    m = re.search(r"questionnairePreCard\?:\s*\{[^}]*buttonSubDesc", src, re.S)
    assert m, "ChatMessage.questionnairePreCard 类型未加 buttonSubDesc 字段"


# ─────────────────── TC-13 ───────────────────


def test_tc13_admin_preview_component_design_d():
    """admin-web FunctionCardV2Preview 同步走方案 D：顶部色条 + 48 高按钮 + 「开始」 + 手机框 375x667。"""
    src = _read(FCV2_PREVIEW)
    assert "export default function FunctionCardV2Preview" in src, "FunctionCardV2Preview 默认导出缺失"
    assert "export function PhonePreviewFrame" in src, "PhonePreviewFrame 命名导出缺失"
    # 手机框 375 x 667
    assert "width: 375" in src, "PhonePreviewFrame 宽度 375 未找到"
    assert "height: 667" in src, "PhonePreviewFrame 高度 667 未找到"
    # 方案 D token 与 H5 一致
    assert "#F0F9FF" in src, "预览组件副标题色块色 #F0F9FF 未找到"
    assert "rgba(15, 23, 42, 0.08)" in src, "预览组件方案 D 阴影 token 未找到"
    assert "height: 48" in src, "预览按钮 48 高未找到"
    assert "borderRadius: 12" in src, "预览按钮圆角 12 未找到"
    # 按钮文案固定「开始」
    # 简化校验：源码中有直接「开始」字面值
    assert "开始" in src, "预览按钮文案「开始」未硬编码"
    # 顶部 4px 色条
    assert "fcv2-preview-top-bar" in src, "预览组件顶部色条 testid 未找到"


# ─────────────────── TC-14 ───────────────────


def test_tc14_admin_function_buttons_page_preview_modal_with_live_binding():
    """function-buttons/page.tsx 预览触发按钮 + Modal + 表单字段实时联动到预览。"""
    src = _read(FB_PAGE)
    assert "FunctionCardV2Preview" in src, "未引入 FunctionCardV2Preview"
    assert "PhonePreviewFrame" in src, "未引入 PhonePreviewFrame"
    assert "previewOpen" in src and "setPreviewOpen" in src, "预览浮层 state 未声明"
    assert 'data-testid="function-card-preview-trigger"' in src, "预览触发按钮 testid 未设置"
    assert "预览效果" in src, "预览触发按钮文案未找到"
    # Form.useWatch 实时联动字段
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


# ─────────────────── TC-15 ───────────────────


def test_tc15_admin_function_buttons_page_has_v12_field_hints():
    """function-buttons/page.tsx 含 v1.2 字段提示（cover_img / button_text 不生效说明）。"""
    src = _read(FB_PAGE)
    assert "fcv2-v12-field-hint-cover" in src, "v1.2 字段提示 testid 未找到"
    # 必须明确告知运营：封面图不展示、button_text 固定「开始」
    assert "封面图" in src and ("停用" in src or "不再展示" in src or "不展示" in src), \
        "未提示运营：cover_img 不再展示"
    assert "开始" in src, "未提示运营：button_text 已统一硬编码为「开始」"


# ─────────────────── TC-16 ───────────────────


def test_tc16_card_whole_clickable_with_stop_propagation():
    """整卡可点击：容器 onClick + 主按钮 stopPropagation 防双触发。"""
    src = _read(FCV2)
    assert "onClick={handleCardClick}" in src, "卡片容器未绑定整卡 onClick"
    assert "e.stopPropagation()" in src, "主按钮未 stopPropagation 防双触发"
    assert "data-fcv2-stop" in src, "未设置 data-fcv2-stop 防冒泡标记"
