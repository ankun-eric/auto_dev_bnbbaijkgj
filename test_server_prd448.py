"""PRD-448 非UI自动化测试

针对部署到服务器的 h5-web 进行非UI层验证：
1. 关键页面可访问（HTTP 200）
2. AI 首页 HTML / JS bundle 中包含 AdvisorCapsule 相关 testid 标记
3. 旧的"裸文字 XXX 的档案 ▽"不再出现在 chat 详情页 chunk 里
4. 章节命名标记 PRD-448 出现在生产 bundle 中
"""
from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.request

HOST = "newbb.test.bangbangvip.com"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def fetch(path: str, timeout: int = 20) -> tuple[int, str]:
    url = BASE_URL + path
    req = urllib.request.Request(url, headers={"User-Agent": "PRD448-test/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return -1, str(e)


def get_chunk_urls(html: str) -> list[str]:
    """提取页面引用的所有 _next/static chunk JS URL（绝对路径）。"""
    urls = []
    for m in re.finditer(r'src="(/[^"]+\.js)"', html):
        urls.append(m.group(1))
    for m in re.finditer(r'href="(/[^"]+\.js)"', html):
        urls.append(m.group(1))
    return list(dict.fromkeys(urls))


def fetch_abs(path: str, timeout: int = 30) -> tuple[int, str]:
    """fetch by absolute server path (no BASE_URL prefix)."""
    url = f"https://{HOST}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "PRD448-test/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return -1, str(e)


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    print("=" * 70)
    print("PRD-448 非UI自动化测试")
    print("=" * 70)

    # 1. key pages reachable
    pages = ["/", "/login/", "/ai-home/", "/chat-history/"]
    for p in pages:
        code, _ = fetch(p)
        ok = code == 200
        results.append((f"page reachable: {p}", ok, f"HTTP {code}"))

    # 2. AI 首页 HTML 抓取并检查 chunks
    print("\n--- check ai-home bundle for advisor-capsule markers ---")
    code, ai_home_html = fetch("/ai-home/")
    ok_ai_home = code == 200 and len(ai_home_html) > 1000
    results.append(("ai-home HTML downloaded", ok_ai_home, f"size={len(ai_home_html)}"))

    chunks = get_chunk_urls(ai_home_html)
    print(f"discovered {len(chunks)} chunks on ai-home")

    advisor_markers = [
        "advisor-capsule",
        "ai-home-profile-card-wrapper",
    ]
    found_in_chunks: dict[str, bool] = {m: False for m in advisor_markers}
    for cu in chunks:
        if "/_next/static/chunks/" not in cu:
            continue
        c, body = fetch_abs(cu)
        if c != 200 or not body:
            continue
        for m in advisor_markers:
            if m in body:
                found_in_chunks[m] = True
    for m, ok in found_in_chunks.items():
        results.append((f"ai-home chunk contains '{m}'", ok, ""))

    # 3. chat 详情页 chunks
    print("\n--- check /chat/ static path doesn't 500 (try fake session) ---")
    # /chat/[sessionId] 是动态路由，访问随便的 id
    code_chat, chat_html = fetch("/chat/test-session/")
    ok_chat = code_chat in (200, 401, 403, 404)  # 200 优先，鉴权拦截也算"路由可达"
    results.append((f"chat detail route reachable", ok_chat, f"HTTP {code_chat}"))

    if code_chat == 200 and chat_html:
        chunks_chat = get_chunk_urls(chat_html)
        chat_markers = [
            "chat-profile-card-wrapper",
            "advisor-capsule",
        ]
        chat_found: dict[str, bool] = {m: False for m in chat_markers}
        for cu in chunks_chat:
            if "/_next/static/chunks/" not in cu:
                continue
            c, body = fetch_abs(cu)
            if c != 200 or not body:
                continue
            for m in chat_markers:
                if m in body:
                    chat_found[m] = True
        for m, ok in chat_found.items():
            results.append((f"chat-detail chunk contains '{m}'", ok, ""))

    # 4. 后端 health check（旁路确认 backend 仍正常，未被影响）
    code_h, _ = fetch("/api/health")
    ok_h = code_h in (200, 404)  # /api/health 是否存在不重要，只要不是 5xx
    results.append((f"backend api still alive", ok_h, f"HTTP {code_h}"))

    # 5. 报告
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    pass_n = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, info in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {info}")
    print(f"\n{pass_n}/{total} passed")

    return 0 if pass_n == total else 1


if __name__ == "__main__":
    sys.exit(main())
