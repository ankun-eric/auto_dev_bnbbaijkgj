"""
[Bug-432-fix Step 0] 后端接口连通性自检
通过宿主 nginx (HTTPS) 直接访问 profile_card / medications 接口，
不带 token => 期望 401（鉴权正确）
带不存在的 consultant_id + 不带 token => 期望 401（先鉴权再业务）
带不存在的 consultant_id + 假 token => 期望 401 或 404
顺便检查 health 与 ai-home-config 服务可达
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

CASES = [
    # (label, path, headers, expected_status_in)
    ("health", "/api/health", {}, [200]),
    ("ai-home-config", "/api/ai-home-config", {}, [200]),
    ("profile_card no token => 401", "/api/v1/consultant/0/profile_card", {}, [401]),
    ("medications no token => 401", "/api/v1/consultant/0/medications", {}, [401]),
    (
        "profile_card 不存在 id + 假 token => 401/404",
        "/api/v1/consultant/999999/profile_card",
        {"Authorization": "Bearer xxxx_invalid_token"},
        [401, 404],
    ),
]


def hit(path: str, headers: dict):
    req = urllib.request.Request(BASE + path, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read()[:500]
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"")[:500]
    except Exception as e:
        return -1, str(e).encode("utf-8")[:500]


def main():
    pass_cnt = 0
    fail = []
    for label, path, headers, expected in CASES:
        code, body = hit(path, headers)
        ok = code in expected
        if ok:
            pass_cnt += 1
            print(f"[PASS] {label}: status={code}")
        else:
            fail.append((label, path, code, expected, body))
            print(f"[FAIL] {label}: status={code} expected={expected} body={body[:200]!r}")
    print(f"\n=== smoke 结果: {pass_cnt}/{len(CASES)} PASS ===")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
