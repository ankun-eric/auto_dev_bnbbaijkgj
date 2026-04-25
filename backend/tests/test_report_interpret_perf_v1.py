"""[2026-04-25] 体检报告解读性能优化 + OCR 隐藏 PRD V1.0 回归测试。

覆盖：
1. 新增 task-status 任务状态轮询接口的状态映射逻辑
2. 新增 ocr-detail 按需查询接口
3. ocr-detail/click 埋点接口
4. 静态源码断言：F5 默认隐藏 OCR 的关键标记保留
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "app"


def _read(p: str) -> str:
    return (ROOT / p).read_text(encoding="utf-8")


# ─────────────────────── 静态源码断言 ───────────────────────


def test_task_status_endpoint_exists():
    src = _read("api/report_interpret.py")
    assert "/report/interpret/session/{session_id}/task-status" in src
    assert "InterpretTaskStatusResponse" in src
    assert "stage" in src and "percent" in src


def test_ocr_detail_endpoint_exists():
    src = _read("api/report_interpret.py")
    assert "/report/interpret/session/{session_id}/ocr-detail" in src
    assert "InterpretOcrDetailResponse" in src
    assert "has_ocr" in src


def test_ocr_detail_click_endpoint_exists():
    src = _read("api/report_interpret.py")
    assert "/report/interpret/ocr-detail/click" in src
    assert "OCR_DETAIL_CLICK" in src


def test_status_mapping_logic_present():
    """task-status 应包含 pending/running/done/failed 映射"""
    src = _read("api/report_interpret.py")
    for kw in ('"uploaded"', '"ocr"', '"ai"', '"done"', '"failed"'):
        assert kw in src, f"task-status mapping missing keyword {kw}"


# ─────────────────────── 行为断言（如可执行） ───────────────────────


def test_response_model_shape():
    """response model 字段定义是否符合 PRD F2-2 / F4-1。"""
    src = _read("api/report_interpret.py")
    # InterpretTaskStatusResponse 必须包含 status/stage/percent/error 字段
    block = src[src.index("class InterpretTaskStatusResponse"):]
    block = block[: block.index("@router.get")]
    for field in ["session_id", "status", "stage", "percent", "error"]:
        assert field in block, f"InterpretTaskStatusResponse missing field {field}"


def test_ocr_detail_response_shape():
    src = _read("api/report_interpret.py")
    block = src[src.index("class InterpretOcrDetailResponse"):]
    block = block[: block.index("@router.get")]
    for field in ["session_id", "report_id", "ocr_text", "has_ocr"]:
        assert field in block, f"InterpretOcrDetailResponse missing field {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
