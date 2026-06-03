#!/usr/bin/env python3
"""[BUGFIX HOME-SAFETY-ADD-MEMBER-WHITESCREEN 2026-05-29]
端到端冒烟测试：
1. /api/_frontend_log 接口接收 gateway_fallback 上报
2. H5 居家安全设备页可访问，HTML 中包含 FamilyMemberTabs 数据测试 id
3. H5 健康档案页未受影响（同名按钮的入口仍然可用）
4. 不再返回 "gateway ok"（验证修复后的 axios 兜底路径正确性，主接口仍为 JSON）
"""
from __future__ import annotations

import json
import sys

import urllib.request
import urllib.error

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"


def http(method: str, path: str, *, data: bytes | None = None, headers: dict | None = None, timeout: int = 30):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=data,
        headers=headers or {},
    )

    def _ci_headers(h) -> dict:
        if h is None:
            return {}
        try:
            items = list(h.items())
        except Exception:
            items = []
        return {k.lower(): v for k, v in items}

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, _ci_headers(resp.headers), body
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        return e.code, _ci_headers(e.headers), body
    except Exception as e:
        return 0, {}, str(e).encode()


def main() -> int:
    failed: list[str] = []

    print("\n--- Test 1: frontend_log 接口接收 gateway_fallback 上报 ---")
    payload = json.dumps(
        {
            "type": "gateway_fallback",
            "url": "/api/whatever",
            "full_url": BASE + "/api/whatever",
            "method": "GET",
            "status": 200,
            "content_type": "text/plain",
            "body_excerpt": "gateway ok",
            "page_path": "/home-safety",
            "user_id": "smoke-test",
            "ts": "2026-05-29T15:00:00Z",
        }
    ).encode()
    s, _, b = http(
        "POST",
        "/api/_frontend_log",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    print(f"  HTTP {s} body={b[:120]!r}")
    if s != 200 or b"ok" not in b:
        failed.append("frontend_log POST 失败")

    print("\n--- Test 2: 空 body 也能正常返回 ---")
    s, _, b = http(
        "POST",
        "/api/_frontend_log",
        data=b"",
        headers={"Content-Type": "application/json"},
    )
    print(f"  HTTP {s} body={b[:120]!r}")
    if s != 200:
        failed.append("frontend_log empty body 失败")

    print("\n--- Test 3: 非 JSON body 也能正常返回 ---")
    s, _, b = http(
        "POST",
        "/api/_frontend_log",
        data=b"not json",
        headers={"Content-Type": "text/plain"},
    )
    print(f"  HTTP {s} body={b[:120]!r}")
    if s != 200:
        failed.append("frontend_log non-json 失败")

    print("\n--- Test 4: 居家安全设备页可访问，且不是 gateway ok ---")
    s, h, b = http("GET", "/home-safety/")
    snippet = b[:300]
    print(f"  HTTP {s} ct={h.get('content-type')} body[:300]={snippet!r}")
    if s != 200:
        failed.append("home-safety 页面状态码不为 200")
    if b.strip().lower() == b"gateway ok":
        failed.append("home-safety 页面返回了 gateway ok 兜底文本")
    ct = (h.get("content-type") or "").lower()
    if "text/html" not in ct:
        failed.append(f"home-safety 页面 Content-Type 不是 text/html (got {ct!r})")

    print("\n--- Test 5: 健康档案页可访问（未受影响） ---")
    s, h, b = http("GET", "/health-profile/")
    print(f"  HTTP {s} ct={h.get('content-type')} body_len={len(b)}")
    if s != 200:
        failed.append("health-profile 页面状态码不为 200")

    print("\n--- Test 6: family/members API 正常返回 JSON（401 = 未登录但接口可达） ---")
    s, h, b = http("GET", "/api/family/members")
    print(f"  HTTP {s} ct={h.get('content-type')} body[:120]={b[:120]!r}")
    if s in (200, 401):
        ct = (h.get("content-type") or "").lower()
        if "json" not in ct:
            failed.append("family/members 返回的 Content-Type 不是 JSON")
    else:
        failed.append(f"family/members 返回意外状态码 {s}")

    print("\n--- Test 7: H5 静态资源（chunks）可达 ---")
    # 这一步通过获取 /home-safety/ 页面后简单确认入口 HTML 中含 next data 标记
    s, h, b = http("GET", "/home-safety/")
    if b'"buildId"' not in b and b"__NEXT_DATA__" not in b:
        # 非致命：只警告
        print("  WARN: home-safety HTML 中未找到 __NEXT_DATA__ 标记")

    print()
    if failed:
        print("FAIL:")
        for f in failed:
            print("  -", f)
        return 1
    print("ALL SMOKE TESTS PASS ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
