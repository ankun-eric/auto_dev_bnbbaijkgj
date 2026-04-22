"""[2026-04-23] 非 UI 自动化测试：验证"接口改造清单"的路由契约。

测试策略（离线契约级）：
- 不需要启动整个 FastAPI + DB，只要能 import 模块并验证新路径已注册。
- 通过 `app.main.app.routes` 做契约检查。
- 覆盖需求清单：新增 6 条、扩展 2 条、prompt_type 常量。
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

# 确保 backend/ 在 sys.path 中，便于 import app.main
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _get_app():
    return importlib.import_module("app.main").app


def _route_exists(app, path: str, method: str) -> bool:
    method = method.upper()
    for r in app.routes:
        rp = getattr(r, "path", None)
        methods = getattr(r, "methods", None) or set()
        if rp == path and method in methods:
            return True
    return False


def test_new_routes_registered():
    app = _get_app()
    # 需求清单里的 6 个新增路由
    assert _route_exists(app, "/api/checkup/compare/create-session", "POST")
    assert _route_exists(app, "/api/chat/sessions/{session_id}/first-message-stream", "GET")
    assert _route_exists(app, "/api/chat/sessions/{session_id}/messages-stream", "POST")
    assert _route_exists(app, "/api/checkup/reports/{report_id}", "GET")
    assert _route_exists(app, "/api/checkup/reports/{report_id}", "PUT")
    assert _route_exists(app, "/api/checkup/reports/{report_id}/ensure-session", "POST")


def test_extended_routes_registered():
    app = _get_app()
    # 新增通用会话详情接口（按需求清单扩展 GET /api/chat/sessions/{id}，
    # 响应包含 report_id / report_ids / family_member / reports_brief）
    assert _route_exists(app, "/api/chat/sessions/{session_id}", "GET")
    # OCR 批量识别接口（响应增加 session_id 字段，由 OcrBatchRecognizeResponse 定义）
    assert _route_exists(app, "/api/ocr/batch-recognize", "POST")


def test_deprecated_routes_still_registered():
    """下线接口保留，但返回 410 Gone（路径仍注册）。"""
    app = _get_app()
    assert _route_exists(app, "/api/report/analyze", "POST")
    # 项目里 trend 是 /report/trend/{indicator_name}（GET）
    assert _route_exists(app, "/api/report/trend/{indicator_name}", "GET")
    # compare 在项目里是 POST（/report/compare）
    assert _route_exists(app, "/api/report/compare", "POST")


def test_prompt_types_accepted():
    """验证 prompt_templates 接受 checkup_report_interpret / checkup_report_compare 类型。"""
    pt = importlib.import_module("app.api.prompt_templates")
    valid = getattr(pt, "VALID_PROMPT_TYPES", None)
    assert valid is not None, "prompt_templates.VALID_PROMPT_TYPES 必须存在"
    assert "checkup_report_interpret" in valid
    assert "checkup_report_compare" in valid


def test_ocr_batch_recognize_has_session_id_field():
    """验证 OcrBatchRecognizeResponse schema 确实含 session_id 字段。"""
    ocr = importlib.import_module("app.api.ocr")
    resp_cls = getattr(ocr, "OcrBatchRecognizeResponse", None)
    assert resp_cls is not None
    fields = getattr(resp_cls, "model_fields", None) or getattr(resp_cls, "__fields__", {})
    assert "session_id" in fields, "OcrBatchRecognizeResponse.session_id 字段必须存在（接口改造清单要求）"


def test_checkup_v2_module_importable():
    """确保新模块 checkup_api_v2 存在且 router prefix 正确。"""
    m = importlib.import_module("app.api.checkup_api_v2")
    router = getattr(m, "router", None)
    assert router is not None
    assert router.prefix == "/api/checkup"
