"""[BUGFIX-FAMILY-DUPLICATE-BIND-V1] 外部 HTTPS 冒烟：关键接口可达性。"""
import requests

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

checks = [
    ("GET", "/api/health", None, {200}),
    ("GET", "/", None, {200, 301, 302, 304}),
    # 核心修复接口：未带 token 应鉴权拦截（401/403），不应 404/5xx
    ("POST", "/api/family/invitation/TESTCODE/accept", {}, {401, 403, 422}),
    # 反向守护接受接口同样应鉴权拦截
    ("GET", "/api/family/management", None, {401, 403}),
]

ok = 0
fail = 0
for method, path, body, expect in checks:
    url = BASE + path
    try:
        if method == "GET":
            r = requests.get(url, timeout=20, allow_redirects=False)
        else:
            r = requests.post(url, json=body, timeout=20, allow_redirects=False)
        status = r.status_code
        result = "OK" if status in expect else "UNEXPECTED"
        if status in expect:
            ok += 1
        else:
            fail += 1
        print(f"[{result}] {method} {path} -> {status} (expect {sorted(expect)})")
    except Exception as e:
        fail += 1
        print(f"[ERROR] {method} {path} -> {e}")

print(f"\n汇总: 可达/符合预期 {ok} / 不符合 {fail}")
