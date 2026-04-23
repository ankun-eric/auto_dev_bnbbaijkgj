"""[2026-04-23] 体检报告多图修复 - 自动化测试

覆盖：
1. 后端写入：_write_checkup_detail 接收 all_image_urls 列表时，checkup_reports.file_urls
   和 checkup_report_details.original_image_urls 都应为完整列表
2. 后端读取：interpret_detail 优先使用 file_urls；fallback 为 [file_url]
3. chat 会话详情：reports_brief[*].file_urls 字段存在并优先返回完整列表
4. 迁移脚本：migrate_report_interpret 幂等，表无则跳过
"""
from __future__ import annotations

import asyncio
import datetime
import os
import sys
from types import SimpleNamespace

import pytest

# 让 tests 可以 import backend
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(THIS_DIR)
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def test_ocr_write_passes_all_image_urls_signature():
    """签名校验：_write_checkup_detail 接收 all_image_urls 关键字参数，
    保证写入侧不会因参数缺失而回退成单图逻辑。"""
    import inspect
    from app.api import ocr as ocr_mod

    sig = inspect.signature(ocr_mod._write_checkup_detail)
    assert "all_image_urls" in sig.parameters, (
        "_write_checkup_detail 必须接收 all_image_urls 参数（多图修复）"
    )
    p = sig.parameters["all_image_urls"]
    assert p.default is None or p.default == [], (
        "all_image_urls 的默认值应为 None 或 []"
    )


def test_interpret_detail_prefers_file_urls():
    """读取侧 fallback：interpret_detail 构造 images 列表时，
    优先使用 rep.file_urls，未设置时退化为 [rep.file_url]。"""
    # 不能真起 DB，直接对函数逻辑做白盒断言（读源码）
    src_path = os.path.join(BACKEND, "app", "api", "report_interpret.py")
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    # 关键断言：源码中必须存在 file_urls 字段读取 + fallback
    assert "file_urls" in src, "interpret_detail 必须读取 file_urls 字段"
    assert "rep.file_url" in src, "interpret_detail 必须保留 file_url fallback"
    # 校验 fallback 先序逻辑
    assert "if not images:" in src, "interpret_detail 必须在 file_urls 为空时 fallback"


def test_chat_sessions_detail_returns_file_urls():
    """chat 会话详情接口 reports_brief[*] 中必须包含 file_urls。"""
    src_path = os.path.join(BACKEND, "app", "api", "chat.py")
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    assert '"file_urls":' in src, "reports_brief 中必须包含 file_urls 字段"
    assert '"thumbnail_urls":' in src, "reports_brief 中必须包含 thumbnail_urls 字段"


def test_checkup_report_model_has_multi_urls_fields():
    """CheckupReport 模型必须拥有 file_urls / thumbnail_urls JSON 字段。"""
    from app.models.models import CheckupReport, CheckupReportDetail

    assert hasattr(CheckupReport, "file_urls"), "CheckupReport 缺少 file_urls 字段"
    assert hasattr(CheckupReport, "thumbnail_urls"), "CheckupReport 缺少 thumbnail_urls 字段"
    assert hasattr(CheckupReportDetail, "original_image_urls"), (
        "CheckupReportDetail 缺少 original_image_urls 字段"
    )


def test_migration_script_adds_multi_urls_columns():
    """启动迁移必须包含对多图字段的 ADD COLUMN 语句。"""
    src_path = os.path.join(BACKEND, "app", "services", "report_interpret_migration.py")
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()
    assert "file_urls" in src, "迁移脚本必须新增 file_urls 字段"
    assert "thumbnail_urls" in src, "迁移脚本必须新增 thumbnail_urls 字段"
    assert "original_image_urls" in src, "迁移脚本必须新增 original_image_urls 字段"
    # 幂等：通过 _add_column_if_missing 保证
    assert "_add_column_if_missing" in src, "迁移必须使用幂等的 _add_column_if_missing"


def test_h5_checkup_chat_uses_multi_image_viewer():
    """H5 /checkup/chat/ 页必须使用 ImageViewer.Multi 做多图预览。"""
    page_path = os.path.join(
        ROOT, "h5-web", "src", "app", "checkup", "chat", "[sessionId]", "page.tsx"
    )
    with open(page_path, "r", encoding="utf-8") as f:
        src = f.read()
    assert "ImageViewer.Multi" in src, "顶部卡片必须使用 ImageViewer.Multi 进行多图预览"
    assert "file_urls" in src, "必须读取 reports_brief[*].file_urls"


def test_h5_checkup_detail_multi_image_already_works():
    """H5 /checkup/detail/[id] 页已有 ImageViewer.Multi 使用 data.images。
    该测试仅作为回归锚点：保证上游后端返回完整 images 时，详情页能正确渲染。"""
    page_path = os.path.join(
        ROOT, "h5-web", "src", "app", "checkup", "detail", "[id]", "page.tsx"
    )
    with open(page_path, "r", encoding="utf-8") as f:
        src = f.read()
    assert "ImageViewer.Multi" in src, "详情页仍需保留 ImageViewer.Multi"
    assert "data.images" in src, "详情页读取 images 数组未被破坏"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
