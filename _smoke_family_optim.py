"""[PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 端到端烟测：H5 关键页面 + 后端配额接口契约。"""
import json
import urllib.request
import ssl

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def post(url, body, headers=None):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=h, method="POST"
    )
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def main():
    fail = 0

    # 1. 邀请页 HTML
    code, body = get(f"{BASE}/family-invite")
    cond = code == 200 and "邀请 TA 加入我的健康守护" in body
    print(f"[H5][family-invite] code={code} hasNewTitle={'邀请 TA 加入我的健康守护' in body} -> {'OK' if cond else 'FAIL'}")
    if not cond:
        fail += 1
        # show first chars
        print(body[:500])

    # 2. 登录拿 token
    try:
        code, body = post(
            f"{BASE}/api/auth/login",
            {"phone": "13800000001", "code": "123456"},
        )
        token = json.loads(body).get("access_token") or json.loads(body).get("token")
        print(f"[Auth] login code={code} token={'YES' if token else 'NO'}")
    except Exception as e:
        token = None
        print(f"[Auth] login FAIL {e}")
        fail += 1

    # 3. 配额接口契约
    if token:
        try:
            code, body = get(
                f"{BASE}/api/family/member/quota",
                headers={"Authorization": f"Bearer {token}"},
            )
            d = json.loads(body)
            keys_ok = all(k in d for k in ("quota_max", "quota_used", "quota_remaining"))
            print(f"[API] quota code={code} keys_ok={keys_ok} payload={d}")
            if code != 200 or not keys_ok:
                fail += 1
        except Exception as e:
            print(f"[API] quota FAIL {e}")
            fail += 1

    print(f"\nFAIL={fail}")
    return fail


if __name__ == "__main__":
    raise SystemExit(main())
