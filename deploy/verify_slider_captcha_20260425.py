"""[2026-04-25] 滑块验证码部署后链接可达性 + 端到端联调验证。"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

LINKS = [
    ("GET", f"{BASE}/api/captcha/slider/issue", "新-滑块挑战"),
    ("GET", f"{BASE}/api/captcha/image", "旧-字符验证码 (用户端 H5 仍用)"),
    ("GET", f"{BASE}/merchant/login", "商家 PC 登录页"),
    ("GET", f"{BASE}/merchant/m/login", "商家 H5 登录页"),
    ("GET", f"{BASE}/admin/login", "管理后台登录页"),
    ("GET", f"{BASE}/login", "用户端 H5 登录页（不应受影响）"),
    ("GET", f"{BASE}/api/health", "后端健康检查"),
]


def head(url: str, method: str = "GET") -> tuple[int, str]:
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "deploy-verify/1.0")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else ""
    except Exception as e:
        return 0, str(e)[:80]


def post_json(url: str, payload: dict) -> tuple[int, dict | str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except Exception:
                return resp.status, body[:200]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body[:300]


def main() -> int:
    print("\n========== 1. 关键链接可达性 ==========")
    pass_count = 0
    for method, url, name in LINKS:
        code, ct = head(url, method)
        ok = code in (200, 201, 405) or (300 <= code < 400)
        flag = "OK" if ok else "X "
        print(f"[{flag}] {code:>3} {name:30s}  {url}")
        if ok:
            pass_count += 1
    print(f"\n通过 {pass_count}/{len(LINKS)}")

    print("\n========== 2. 滑块验证码端到端联调 ==========")
    code, body = head(f"{BASE}/api/captcha/slider/issue")
    print(f"[2.1] issue HTTP {code}")
    req = urllib.request.Request(f"{BASE}/api/captcha/slider/issue")
    with urllib.request.urlopen(req, timeout=20) as resp:
        challenge = json.loads(resp.read().decode("utf-8"))
    cid = challenge["challenge_id"]
    print(f"     challenge_id={cid[:16]}... bg={challenge['bg_width']}x{challenge['bg_height']} puzzle={challenge['puzzle_size']}")
    print(f"     bg_image len={len(challenge['bg_image_base64'])}, puzzle_image len={len(challenge['puzzle_image_base64'])}")

    print("\n[2.2] 故意错位置 (x=10) → 应 ok=false position_mismatch")
    code, resp = post_json(f"{BASE}/api/captcha/slider/verify", {
        "challenge_id": cid,
        "x": 10,
        "trail": [{"x": i*2, "y": (i % 3), "t": i*60} for i in range(15)],
    })
    print(f"     HTTP {code} → {resp}")

    print("\n[2.3] 故意瞬移 (x 一步到位) → 应 ok=false trail_invalid")
    # 拿新 challenge 避免锁
    req = urllib.request.Request(f"{BASE}/api/captcha/slider/issue")
    with urllib.request.urlopen(req, timeout=20) as resp:
        challenge2 = json.loads(resp.read().decode("utf-8"))
    code, resp = post_json(f"{BASE}/api/captcha/slider/verify", {
        "challenge_id": challenge2["challenge_id"],
        "x": 100,
        "trail": [{"x": 0, "y": 0, "t": 0}, {"x": 100, "y": 0, "t": 50}],
    })
    print(f"     HTTP {code} → {resp}")

    print("\n[2.4] 不存在的 challenge_id → 应 challenge_expired")
    code, resp = post_json(f"{BASE}/api/captcha/slider/verify", {
        "challenge_id": "not-exist-id-zzz",
        "x": 100,
        "trail": [{"x": i*5, "y": (i % 2), "t": i*40} for i in range(15)],
    })
    print(f"     HTTP {code} → {resp}")

    print("\n[2.5] 用错误 captcha_token 登录 → 应失败提示验证已过期")
    code, resp = post_json(f"{BASE}/api/merchant/v1/login", {
        "phone": "13900000001",
        "password": "any",
        "captcha_token": "tok_invalid_xxx",
    })
    print(f"     HTTP {code} → {resp}")

    print("\n[2.6] 用错误 captcha_token 走 admin 登录 → 应失败")
    code, resp = post_json(f"{BASE}/api/admin/login", {
        "phone": "13900000001",
        "password": "any",
        "captcha_token": "tok_invalid_xxx",
    })
    print(f"     HTTP {code} → {resp}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
