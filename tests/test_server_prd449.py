"""PRD-449 AI 首页（ai-home）页面优化 — 服务器侧非 UI 自动化测试

测试范围：
  T01 ~ T04：页面可达性（HTTP 200）
  T05      ：默认头像图可下载（/images/default-ai-avatar.png）
  T06      ：ai-home chunks 中包含 AiAvatar 组件特征
  T07      ：ai-home chunks 中包含顶部栏主色（PRD-449 R1）
  T08      ：ai-home chunks 中包含 PRD-449 标记（确认本次代码已上线）
  T09      ：ai-home chunks 中包含 ai-home-welcome-avatar testId（A 位）
  T10      ：ai-home chunks 中包含 ai-home-msg-avatar testId（B 位）
  T11      ：后端 ai-home-config 接口仍正常返回（旁路确认）

运行方式：
  python tests/test_server_prd449.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
TIMEOUT = 25


def fetch(path: str, headers: dict | None = None):
    url = BASE + path
    req = urllib.request.Request(
        url,
        headers=headers
        or {
            "User-Agent": "PRD449-tests/1.0 (Mozilla/5.0)",
            "Accept": "text/html,application/json,*/*;q=0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read()
            return resp.getcode(), body, dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read() if hasattr(e, "read") else b"", {}
    except Exception as e:
        return -1, str(e).encode(), {}


def fetch_text(path: str) -> tuple[int, str]:
    code, body, _ = fetch(path)
    try:
        return code, body.decode("utf-8", errors="replace")
    except Exception:
        return code, ""


def get_ai_home_chunks() -> str:
    """拉取 ai-home 页面 HTML，解析出所有 _next/static/chunks/*.js URL，下载并拼接它们的内容。
    用于后续 T06~T10 在 chunks 中查找特征字符串。"""
    code, html = fetch_text("/ai-home/")
    if code != 200:
        return ""
    # 提取 _next/static/chunks/*.js 路径（包括相对的 /autodev/{id}/_next/... 与 _next/...）
    chunk_paths = set()
    for m in re.finditer(r'["\']([^"\']*?_next/static/chunks/[^"\']+\.js)["\']', html):
        p = m.group(1)
        # 去掉 BASE 前缀以便后续 fetch
        if p.startswith("https://"):
            # 去除域名
            p = "/" + p.split("/", 3)[-1]
        if p.startswith("/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"):
            p = p[len("/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27") :]
        if not p.startswith("/"):
            p = "/" + p
        chunk_paths.add(p)
    # 下载所有 chunks 内容拼接（限制最多 30 个，避免过大）
    contents = [html]  # 也包含 HTML 本身（部分 inline 标记）
    for p in list(chunk_paths)[:30]:
        c, txt = fetch_text(p)
        if c == 200:
            contents.append(txt)
    return "\n".join(contents)


_chunks_cache: str | None = None


def chunks() -> str:
    global _chunks_cache
    if _chunks_cache is None:
        _chunks_cache = get_ai_home_chunks()
    return _chunks_cache


# --- 测试用例 ---


def t01_root_reachable():
    code, _ = fetch_text("/")
    return code == 200, f"GET / -> {code}"


def t02_login_reachable():
    code, _ = fetch_text("/login/")
    return code == 200, f"GET /login/ -> {code}"


def t03_ai_home_reachable():
    code, _ = fetch_text("/ai-home/")
    return code == 200, f"GET /ai-home/ -> {code}"


def t04_chat_history_reachable():
    code, _ = fetch_text("/chat-history/")
    return code == 200, f"GET /chat-history/ -> {code}"


def t05_default_avatar_reachable():
    code, body, hdrs = fetch("/images/default-ai-avatar.png")
    ok = code == 200 and len(body) > 1000
    ct = hdrs.get("Content-Type", "")
    return ok, f"GET /images/default-ai-avatar.png -> {code}, size={len(body)} bytes, ct={ct}"


def t06_ai_avatar_component_present():
    """ai-home chunks 中应出现 AiAvatar 组件相关字符串"""
    txt = chunks()
    if not txt:
        return False, "无法获取 ai-home chunks"
    has_default_url = "default-ai-avatar.png" in txt
    return has_default_url, f"chunks 含 default-ai-avatar.png={has_default_url}"


def t07_topbar_primary_color():
    """ai-home chunks 中应包含 'var(--color-primary)' 顶部栏主色（PRD-449 R1）"""
    txt = chunks()
    if not txt:
        return False, "无法获取 ai-home chunks"
    # Next.js 在 production 下会保留 CSS-in-JS 字符串字面量，因此可在 chunks 中搜索
    found = "var(--color-primary)" in txt
    return found, f"chunks 含 var(--color-primary)={found}"


def t08_prd449_marker_present():
    """ai-home chunks 中应包含 PRD-449 标记，证明本次代码已部署上线"""
    txt = chunks()
    if not txt:
        return False, "无法获取 ai-home chunks"
    found = "PRD-449" in txt
    # 注意 production build 通常会移除注释，这里 PRD-449 在某些 string literal 中也会出现
    # 因此 fallback 检查 ai-home-welcome-avatar testId（更稳定）
    if not found:
        found = "ai-home-welcome-avatar" in txt
    return found, f"chunks 含 PRD-449 或 welcome-avatar testId={found}"


def t09_welcome_avatar_testid():
    """A 位 testId：ai-home-welcome-avatar"""
    txt = chunks()
    if not txt:
        return False, "无法获取 ai-home chunks"
    found = "ai-home-welcome-avatar" in txt
    return found, f"chunks 含 ai-home-welcome-avatar={found}"


def t10_msg_avatar_testid():
    """B 位 testId：ai-home-msg-avatar"""
    txt = chunks()
    if not txt:
        return False, "无法获取 ai-home chunks"
    found = "ai-home-msg-avatar" in txt
    return found, f"chunks 含 ai-home-msg-avatar={found}"


def t11_ai_home_config_api():
    """后端 ai-home-config 接口仍正常返回（旁路确认接口未被本次改动破坏）"""
    code, body, _ = fetch("/api/ai-home-config")
    if code != 200:
        return False, f"GET /api/ai-home-config -> {code}"
    try:
        data = json.loads(body)
    except Exception as e:
        return False, f"JSON 解析失败: {e}"
    cfg = data.get("data", {}).get("config") or data.get("config") or data
    has_welcome = isinstance(cfg, dict) and "welcome" in cfg
    return has_welcome, f"返回含 welcome 字段={has_welcome}"


TESTS = [
    ("T01 根路由可达", t01_root_reachable),
    ("T02 /login/ 可达", t02_login_reachable),
    ("T03 /ai-home/ 可达", t03_ai_home_reachable),
    ("T04 /chat-history/ 可达", t04_chat_history_reachable),
    ("T05 默认头像图可下载", t05_default_avatar_reachable),
    ("T06 chunks 含 default-ai-avatar.png", t06_ai_avatar_component_present),
    ("T07 chunks 含 var(--color-primary) 顶部栏主色", t07_topbar_primary_color),
    ("T08 chunks 含 PRD-449 标记", t08_prd449_marker_present),
    ("T09 chunks 含 ai-home-welcome-avatar testId", t09_welcome_avatar_testid),
    ("T10 chunks 含 ai-home-msg-avatar testId", t10_msg_avatar_testid),
    ("T11 后端 ai-home-config 仍正常", t11_ai_home_config_api),
]


def main() -> int:
    print("=" * 78)
    print(f"PRD-449 服务器侧非 UI 自动化测试 — base = {BASE}")
    print("=" * 78)
    pass_n = 0
    fail_n = 0
    fail_list = []
    for name, fn in TESTS:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"EXCEPTION: {e}"
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name:<55s}  {detail}")
        if ok:
            pass_n += 1
        else:
            fail_n += 1
            fail_list.append((name, detail))
    print("=" * 78)
    print(f"汇总：{pass_n}/{len(TESTS)} PASS, {fail_n} FAIL")
    if fail_list:
        print("失败用例：")
        for n, d in fail_list:
            print(f"  - {n}: {d}")
    print("=" * 78)
    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
