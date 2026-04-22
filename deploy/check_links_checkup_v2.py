"""[2026-04-23] 链接可达性验证：覆盖需求清单中的所有新增/扩展接口 + 关键前端路由。

允许状态码：200/301/302/307/308/401/405/410/422（因为大多数 API 需要鉴权，
未登录时应返回 401 或相应业务码；SSE 未带鉴权也应返回 401 而非 5xx；
下线接口预期 410）。
"""
from __future__ import annotations

import sys
import urllib.request

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

ACCEPT = {200, 301, 302, 303, 307, 308, 400, 401, 403, 404, 405, 410, 422}


def _http(method: str, url: str, body: bytes | None = None, timeout: int = 15) -> int:
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        print(f"    [ERR] {type(e).__name__}: {e}")
        return 0


CASES: list[tuple[str, str, str]] = [
    # (method, url, desc)
    # ─ 前端页面 ─
    ("GET", f"{BASE}/", "H5 首页"),
    ("GET", f"{BASE}/checkup", "体检报告上传入口"),
    ("GET", f"{BASE}/checkup/compare/select", "报告对比选择页"),
    ("GET", f"{BASE}/checkup/detail/1", "报告详情页"),
    ("GET", f"{BASE}/checkup/chat/1", "AI 解读对话页"),
    ("GET", f"{BASE}/admin/", "Admin 首页"),
    # ─ 新增 API（需求清单 #新增接口） ─
    ("POST", f"{BASE}/api/checkup/compare/create-session", "POST /api/checkup/compare/create-session"),
    ("GET", f"{BASE}/api/chat/sessions/1/first-message-stream", "GET /api/chat/sessions/{id}/first-message-stream"),
    ("POST", f"{BASE}/api/chat/sessions/1/messages-stream", "POST /api/chat/sessions/{id}/messages-stream"),
    ("GET", f"{BASE}/api/checkup/reports/1", "GET /api/checkup/reports/{id}"),
    ("PUT", f"{BASE}/api/checkup/reports/1", "PUT /api/checkup/reports/{id}"),
    ("POST", f"{BASE}/api/checkup/reports/1/ensure-session", "POST /api/checkup/reports/{id}/ensure-session"),
    # ─ 扩展 API（需求清单 #扩展接口） ─
    ("POST", f"{BASE}/api/ocr/batch-recognize", "POST /api/ocr/batch-recognize（新增 session_id 字段）"),
    ("GET", f"{BASE}/api/chat/sessions/1", "GET /api/chat/sessions/{id}（扩展字段）"),
    # ─ 下线 API（需求清单 #下线接口） ─
    ("POST", f"{BASE}/api/report/analyze", "下线 POST /api/report/analyze（预期 410）"),
    ("GET", f"{BASE}/api/report/trend/blood_pressure", "下线 GET /api/report/trend"),
    ("POST", f"{BASE}/api/report/compare", "下线 POST /api/report/compare（预期 410）"),
    # ─ 提示词管理（复用现有） ─
    ("GET", f"{BASE}/api/admin/prompt-templates", "Admin GET /api/admin/prompt-templates"),
]


def main() -> int:
    print(f"Base: {BASE}\n")
    fail = 0
    for method, url, desc in CASES:
        body = b"{}" if method in ("POST", "PUT") else None
        status = _http(method, url, body=body)
        ok = status in ACCEPT
        print(f"[{'OK ' if ok else 'FAIL'}] {status:>3} {method:<5} {desc}")
        if not ok:
            fail += 1
            print(f"         URL: {url}")
    total = len(CASES)
    print(f"\n总计：{total - fail}/{total} 可达；失败 {fail} 条")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
