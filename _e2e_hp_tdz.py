"""[BUGFIX-HEALTH-PROFILE-CLIENT-CRASH 2026-05-29] E2E：用 Playwright 真实加载页面，
监听 console error / page error，验证不再出现 ReferenceError TDZ。
"""
import asyncio
import sys
from playwright.async_api import async_playwright

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(ignore_https_errors=True)
        page = await ctx.new_page()
        errors = []
        page_errors = []

        page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        # 路径 1：health-profile
        print(f"\n[路径 1] 访问 {BASE}/health-profile/")
        try:
            resp = await page.goto(f"{BASE}/health-profile/", wait_until="networkidle", timeout=45000)
            print(f"  HTTP: {resp.status if resp else 'N/A'}")
        except Exception as e:
            print(f"  goto 异常: {e}")
        await page.wait_for_timeout(3000)
        body_text = await page.locator("body").inner_text()
        has_crash = "Application error" in body_text or "client-side exception" in body_text
        print(f"  body 含 client-side exception: {has_crash}")
        print(f"  body 长度: {len(body_text)}, 前200字: {body_text[:200]!r}")

        # 路径 2：ai-home
        print(f"\n[路径 2] 访问 {BASE}/ai-home")
        await page.goto(f"{BASE}/ai-home", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        body_text2 = await page.locator("body").inner_text()
        has_crash2 = "Application error" in body_text2 or "client-side exception" in body_text2
        print(f"  body 含 client-side exception: {has_crash2}")

        print(f"\n--- console errors ({len(errors)}) ---")
        for e in errors[:20]:
            print(f"  {e}")
        print(f"\n--- page errors ({len(page_errors)}) ---")
        for e in page_errors[:20]:
            print(f"  {e}")

        # 关键判定：必须没有 ReferenceError 也没有 client-side exception
        tdz_errors = [e for e in (errors + page_errors) if "ReferenceError" in e or "before initialization" in e]
        if tdz_errors:
            print(f"\n[FAIL] 仍有 TDZ 类错误: {tdz_errors}")
            await browser.close()
            return False
        if has_crash:
            print("\n[FAIL] /health-profile/ 仍崩溃")
            await browser.close()
            return False
        print("\n[PASS] 无 TDZ、无 client-side exception")
        await browser.close()
        return True


ok = asyncio.run(main())
sys.exit(0 if ok else 1)
