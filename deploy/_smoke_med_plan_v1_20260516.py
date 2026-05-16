"""[PRD-MED-PLAN-V1 2026-05-16] 部署后线上 Smoke 测试。

仅做接口存在性 + 鉴权一致性探活（无 token 应 401）。
不做端到端业务测试（需登录态），覆盖以单测 + 容器内集成测试。
"""
import json
import urllib.request
import urllib.error
import ssl

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

EXPECTED_AUTH_REQUIRED = [
    # 期望 401（已部署、需登录态）
    "/api/health-plan/medications/list",
    "/api/prd469/medication-ai-call",
    "/api/prd469/care/medication-ai-call",
    "/api/prd469/reminder-setting",
]

PUBLIC_PAGES = [
    # 期望 200
    "/medication-plans",
]


def probe(url: str) -> int:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        print(f"[ERR] {url} {e}")
        return -1


def main():
    failed = 0
    print("=== Endpoint smoke (expect 401) ===")
    for path in EXPECTED_AUTH_REQUIRED:
        url = BASE + path
        code = probe(url)
        ok = code in (401, 403)
        print(f"  {code} {'OK' if ok else 'FAIL'} {path}")
        if not ok:
            failed += 1

    print("\n=== Public page smoke (expect 200) ===")
    for path in PUBLIC_PAGES:
        url = BASE + path
        code = probe(url)
        ok = code == 200
        print(f"  {code} {'OK' if ok else 'FAIL'} {path}")
        if not ok:
            failed += 1

    print(f"\n[SMOKE] failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
