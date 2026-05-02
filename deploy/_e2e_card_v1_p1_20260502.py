# -*- coding: utf-8 -*-
"""[2026-05-02 卡功能 v1.1 第 1 期] 生产域名 E2E 端到端测试

覆盖：
1. 注册一个测试用户、登录拿 token
2. /api/cards 公开列表（200）
3. /api/cards/me/wallet 需登录（401 -> 登录后 200）
4. /api/cards/by-product/<id> 商品的可用卡推荐（200）
5. /api/admin/cards 鉴权检查（不带 token 401，带普通用户 token 403）

注意：admin 写操作（创建卡 / 上下架 / 删除）已在本地 pytest 中完整覆盖（17/17 全通过），
此处 E2E 主要验证生产环境的部署、路由、鉴权链路是否正常。
"""
from __future__ import annotations
import json
import sys
import time
import urllib.parse
import urllib.request
import ssl


BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
TIMEOUT = 30
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def req(method: str, path: str, *, headers: dict | None = None, body: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE}{path}"
    data = None
    h = {"Accept": "application/json"}
    if headers:
        h.update(headers)
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=TIMEOUT, context=CTX) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, (json.loads(raw) if raw.strip() else {})
            except Exception:
                return resp.status, {"_raw": raw[:300]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, (json.loads(raw) if raw.strip() else {})
        except Exception:
            return e.code, {"_raw": raw[:300]}


def passed(name: str):
    print(f"  [PASS] {name}", flush=True)


def failed(name: str, msg: str):
    print(f"  [FAIL] {name} :: {msg}", flush=True)


def main() -> int:
    ts = int(time.time())
    phone = f"13{ts % 10**9:09d}"
    fails: list[str] = []

    print(f"== E2E 测试目标：{BASE} ==", flush=True)
    print(f"== 测试用户手机号：{phone} ==", flush=True)

    # ─── 1. /api/cards 公开 ───
    print("\n[1] /api/cards 公开访问")
    code, data = req("GET", "/api/cards?page=1&page_size=10")
    if code == 200 and "items" in data and "total" in data:
        passed(f"GET /api/cards 200, total={data['total']}, items={len(data['items'])}")
    else:
        failed("GET /api/cards", f"code={code} data={str(data)[:200]}")
        fails.append("cards_list")

    # ─── 2. /api/cards/me/wallet 未登录 → 401 ───
    print("\n[2] /api/cards/me/wallet 未登录应 401")
    code, _ = req("GET", "/api/cards/me/wallet")
    if code == 401:
        passed("GET /api/cards/me/wallet 401（未登录）")
    else:
        failed("GET /api/cards/me/wallet (no token)", f"code={code}")
        fails.append("wallet_auth_missing")

    # ─── 3. /api/admin/cards 未登录 → 401 ───
    print("\n[3] /api/admin/cards 未登录应 401")
    code, _ = req("GET", "/api/admin/cards")
    if code == 401:
        passed("GET /api/admin/cards 401（未登录）")
    else:
        failed("GET /api/admin/cards (no token)", f"code={code}")
        fails.append("admin_auth_missing")

    # ─── 4. 注册一个测试用户 + 登录 ───
    print("\n[4] 注册并登录测试用户")
    code, data = req("POST", "/api/auth/register", body={
        "phone": phone, "password": "test1234", "nickname": f"卡测试-{ts % 1000}",
    })
    if code in (200, 201):
        passed(f"register ok ({code})")
    else:
        # 已存在 / 短信限制等
        failed("register", f"code={code} data={str(data)[:200]}")
        # 仍然尝试登录
    code, data = req("POST", "/api/auth/login", body={
        "phone": phone, "password": "test1234",
    })
    token = data.get("access_token") if isinstance(data, dict) else None
    if code == 200 and token:
        passed("login ok, got access_token")
    else:
        failed("login", f"code={code} data={str(data)[:200]}")
        fails.append("login")
        return _summary(fails)

    auth = {"Authorization": f"Bearer {token}"}

    # ─── 5. 登录后访问卡包 → 200 + 0 张卡 ───
    print("\n[5] /api/cards/me/wallet 登录后应 200")
    code, data = req("GET", "/api/cards/me/wallet", headers=auth)
    if code == 200 and "items" in data and "expired_count" in data:
        passed(f"GET /api/cards/me/wallet 200, total={data.get('total')} unused={data.get('unused_count')}")
    else:
        failed("GET /api/cards/me/wallet (with token)", f"code={code} data={str(data)[:200]}")
        fails.append("wallet_with_token")

    # ─── 6. 普通用户访问 admin → 403 ───
    print("\n[6] /api/admin/cards 普通用户应 403")
    code, _ = req("GET", "/api/admin/cards", headers=auth)
    if code == 403:
        passed("GET /api/admin/cards 403（普通用户）")
    else:
        failed("GET /api/admin/cards (user token)", f"code={code}")
        fails.append("admin_forbidden")

    # ─── 7. 商品的可用卡推荐：随便挑一个商品 ID = 1（有则正常 200，无则也应 404 不应 500） ───
    print("\n[7] /api/cards/by-product/1")
    code, data = req("GET", "/api/cards/by-product/1")
    if code in (200, 404) and isinstance(data, dict):
        passed(f"GET /api/cards/by-product/1 code={code}")
    else:
        failed("GET /api/cards/by-product/1", f"code={code} data={str(data)[:200]}")
        fails.append("by_product")

    return _summary(fails)


def _summary(fails: list[str]) -> int:
    print("\n" + "=" * 60, flush=True)
    if fails:
        print(f"[FAIL] E2E 失败项数：{len(fails)} -> {fails}", flush=True)
        return 1
    print("[PASS] ALL E2E PASSED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
