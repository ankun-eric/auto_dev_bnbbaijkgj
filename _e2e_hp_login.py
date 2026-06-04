"""[BUGFIX-HEALTH-PROFILE-CLIENT-CRASH 2026-05-29] E2E with login：
真实登录后访问健康档案、AI 首页，验证 3 条冒烟路径。
"""
import asyncio
import re
import sys
import requests

from playwright.async_api import async_playwright

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
API = f"{BASE}/api"
TEST_PHONE = "13800000001"
TEST_CODE = "123456"


def login_get_token():
    s = requests.Session()
    s.verify = False
    r = s.post(f"{API}/auth/sms-code", json={"phone": TEST_PHONE, "type": "login"})
    r.raise_for_status()
    r = s.post(f"{API}/auth/sms-login", json={"phone": TEST_PHONE, "code": TEST_CODE})
    r.raise_for_status()
    return r.json()["access_token"]


async def main():
    print("[step 1] 登录拿 token ...")
    token = login_get_token()
    print(f"  token={token[:30]}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        )
        # 注入 token 到 localStorage
        await ctx.add_init_script(f"""
          localStorage.setItem('token', '{token}');
          localStorage.setItem('access_token', '{token}');
        """)
        page = await ctx.new_page()
        console_errors = []
        page_errors = []
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        # === 冒烟路径 1：进 /health-profile/ 不白屏 ===
        print(f"\n[路径 1] /health-profile/ ...")
        r = await page.goto(f"{BASE}/health-profile/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(4500)
        body = await page.locator("body").inner_text()
        has_app_err = "Application error" in body or "client-side exception" in body
        # 是否成功渲染到健康档案的核心元素？（例如成员 tab 或 hero）
        is_login_page = "AI 健康管家" in body and "获取验证码" in body and "登录" in body
        is_archive_page = ("健康档案" in body) or ("我的档案" in body) or ("成员" in body and "本人" in body)
        print(f"  HTTP={r.status if r else 'N/A'}, 含异常={has_app_err}, 在登录页={is_login_page}, 在档案页={is_archive_page}")

        # === 冒烟路径 2：AI 首页 ===
        print(f"\n[路径 2] /ai-home ...")
        r = await page.goto(f"{BASE}/ai-home", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        body2 = await page.locator("body").inner_text()
        has_app_err2 = "Application error" in body2 or "client-side exception" in body2
        print(f"  HTTP={r.status if r else 'N/A'}, 含异常={has_app_err2}")

        # === 冒烟路径 3：family 页面 ===
        print(f"\n[路径 3] /family/ ...")
        r = await page.goto(f"{BASE}/family/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2500)
        body3 = await page.locator("body").inner_text()
        has_app_err3 = "Application error" in body3 or "client-side exception" in body3
        print(f"  HTTP={r.status if r else 'N/A'}, 含异常={has_app_err3}")

        print(f"\n--- page errors ({len(page_errors)}) ---")
        for e in page_errors[:30]:
            print(f"  {e}")

        # 关键判定
        tdz = [e for e in (console_errors + page_errors) if "ReferenceError" in e or "before initialization" in e]
        if tdz:
            print(f"\n[FAIL] 仍有 TDZ 类错误: {tdz}")
            await browser.close()
            return False
        if has_app_err or has_app_err2 or has_app_err3:
            print("\n[FAIL] 某页面仍有 client-side exception")
            await browser.close()
            return False
        if not is_archive_page and not is_login_page:
            print("\n[WARN] /health-profile/ 既不是档案页也不是登录页：可能渲染异常")
        print("\n[PASS] 3 条冒烟路径全部通过：无 TDZ、无 client-side exception")
        await browser.close()
        return True


ok = asyncio.run(main())
sys.exit(0 if ok else 1)
