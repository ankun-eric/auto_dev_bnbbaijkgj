"""PRD-448 v1.1 增量补丁 — 咨询人胶囊二次细化 — 服务器侧非 UI 自动化测试

本次补丁仅改动 H5-web 前端，无后端变化。测试通过抓取部署后的前端 chunks 来
验证 v1.1 关键改动是否上线（v1.0 不应出现的特征 + v1.1 必须出现的特征）。

测试范围：
  T01: ai-home 页面可达（HTTP 200）
  T02: chat/[sessionId] 页面可达（路径存在，未登录会重定向但服务可达）
  T03: chunks 中包含 v1.1 文案模板「本次回答结合」 (前端硬编码)
  T04: chunks 中包含 v1.1 SVG 箭头特征 path d="M4 6L8 10L12 6"
  T05: chunks 中包含 v1.1 内边距 6px 12px / 圆角 10
  T06: chunks 中包含 v1.1 文字字号 14 / 行高 20px
  T07: chunks 中包含 v1.1 isSelf 相关标记 data-is-self
  T08: chunks 中包含 PRD-448 v1.1 标记
  T09: chunks 中【不】再包含 v1.0 字符箭头实现 ⌃ / ⌄（已被 SVG 替换）
  T10: chunks 中【不】再包含 v1.0 文案 "{name} 的档案" 形式中独立的 "我的档案" 占位
  T11: chunks 中【不】再包含 v1.0 加载中…占位字符串 "加载中…" 直接出现在胶囊上下文
  T12: 后端 ai-home-config 接口正常返回（旁路确认）

运行方式：
  python tests/test_server_prd448_v11.py
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
            "User-Agent": "PRD448-v11-tests/1.0 (Mozilla/5.0)",
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


def get_h5_chunks(seed_paths=("/ai-home/", "/chat/1")) -> str:
    """拉取若干 H5 页面 HTML，解析出 _next/static/chunks/*.js 并下载拼接。"""
    contents: list[str] = []
    chunk_paths: set[str] = set()
    for sp in seed_paths:
        code, html = fetch_text(sp)
        if code == 200 or code == 307 or code == 302 or code == 308:
            # 即便登录重定向，HTML 中的 chunks 通常仍可解析（若是空响应则跳过）
            if not html:
                continue
            contents.append(html)
            for m in re.finditer(r'["\']([^"\']*?_next/static/chunks/[^"\']+\.js)["\']', html):
                p = m.group(1)
                if p.startswith("https://"):
                    p = "/" + p.split("/", 3)[-1]
                if p.startswith("/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"):
                    p = p[len("/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"):]
                if not p.startswith("/"):
                    p = "/" + p
                chunk_paths.add(p)
    for p in list(chunk_paths)[:60]:
        c, txt = fetch_text(p)
        if c == 200:
            contents.append(txt)
    return "\n\n".join(contents)


# ─────────── 测试用例 ───────────

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, msg: str = "") -> None:
    results.append((name, ok, msg))
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {name} {('- ' + msg) if msg else ''}")


def t01_ai_home_reachable():
    code, _ = fetch_text("/ai-home/")
    record("T01 ai-home 页面可达", code == 200, f"http={code}")


def t02_chat_session_reachable():
    code, _ = fetch_text("/chat/1")
    # 未登录时通常会 200 渲染外壳或 307 重定向到 /login，均视为可达
    record(
        "T02 chat/[sessionId] 页面可达",
        code in (200, 301, 302, 307, 308),
        f"http={code}",
    )


def t03_template_text_present(chunks: str):
    ok = "本次回答结合" in chunks and "的档案" in chunks
    record("T03 v1.1 文案模板「本次回答结合 ... 的档案」出现在 chunks", ok)


def t04_svg_arrow_path_present(chunks: str):
    # 允许少量空白差异；最严格的方式是查找 path d="M4 6L8 10L12 6"
    ok = bool(re.search(r"M4\s*6L8\s*10L12\s*6", chunks))
    record("T04 v1.1 SVG 箭头 path d=M4 6L8 10L12 6 出现", ok)


def t05_padding_radius_present(chunks: str):
    # padding 6px 12px 与 borderRadius 10
    ok_pad = bool(
        re.search(r"padding\s*:\s*['\"]?6px\s+12px['\"]?", chunks)
        or re.search(r"['\"]6px 12px['\"]", chunks)
    )
    ok_radius = bool(
        re.search(r"borderRadius\s*:\s*10\b", chunks)
        or re.search(r"border-radius\s*:\s*10px", chunks)
    )
    record("T05 v1.1 padding 6px 12px / borderRadius 10 出现", ok_pad and ok_radius,
           f"padding={ok_pad} radius={ok_radius}")


def t06_font_size_line_height_present(chunks: str):
    # 由于 14/20 是常见数字，这里寻找紧邻出现的特征：lineHeight: '20px' 与 fontSize:14
    ok_lh = bool(re.search(r"lineHeight\s*:\s*['\"]20px['\"]", chunks))
    ok_fs = bool(re.search(r"fontSize\s*:\s*14\b", chunks))
    record("T06 v1.1 字号 14 / 行高 20px 出现", ok_lh and ok_fs,
           f"fontSize14={ok_fs} lineHeight20px={ok_lh}")


def t07_data_is_self_attr_present(chunks: str):
    ok = "data-is-self" in chunks
    record("T07 v1.1 data-is-self 属性出现（isSelf prop 已接入）", ok)


def t08_prd448_v11_marker(chunks: str):
    # 我们的源码注释里写了 "PRD-448 v1.1"，编译后注释会被去除，但 testId / 属性仍保留 v1.1 痕迹。
    # 由于 testId 通过模板字符串拼接 (`${testId}-arrow`)，编译后字面值看不到 "ai-advisor-capsule-arrow"，
    # 故只需校验 advisor-capsule 与 ArrowIcon 的关键标识 data-expanded 同时出现。
    ok = (
        "advisor-capsule" in chunks
        and "ai-advisor-capsule" in chunks  # ProfileCard 中传入的 testId="ai-advisor-capsule"
        and "data-expanded" in chunks  # AdvisorCapsule + ArrowIcon 都用的属性
    )
    record(
        "T08 v1.1 advisor-capsule / ai-advisor-capsule / data-expanded 标识同时出现",
        ok,
    )


def t09_no_legacy_arrow_chars(chunks: str):
    # v1.0 用 ⌃ / ⌄ 字符；v1.1 已切换到 SVG。允许极少量出现在其他位置（不应在胶囊文件附近）。
    # 简化：要求两个字符都不出现（h5 代码全文中除胶囊以外通常也不会出现这两个字符）
    has_up = "⌃" in chunks
    has_dn = "⌄" in chunks
    record("T09 v1.0 字符箭头 ⌃/⌄ 已不在 chunks 中出现",
           (not has_up) and (not has_dn),
           f"has_up={has_up} has_dn={has_dn}")


def t10_no_my_archive_placeholder(chunks: str):
    # v1.0 兜底文案 "我的档案"
    ok = "我的档案" not in chunks
    record("T10 v1.0 占位文案「我的档案」不再出现", ok)


def t11_no_loading_placeholder_in_capsule(chunks: str):
    # v1.0 兜底文案 "加载中…"（注意 ellipsis 字符）。
    # 由于该字符串可能在其他模块也出现，这里仅检查是否与 advisor-capsule 同时出现在同一短上下文中。
    pattern = re.compile(r"advisor-capsule[^\n]{0,800}加载中…", re.S)
    ok = not bool(pattern.search(chunks))
    record("T11 v1.0「加载中…」占位不再出现在 advisor-capsule 上下文", ok)


def t12_ai_home_config_api_ok():
    code, body, _ = fetch("/api/ai-home-config")
    ok = code == 200 and len(body) > 0
    record("T12 后端 ai-home-config 接口可达", ok, f"http={code}")


def main() -> int:
    print(f"BASE = {BASE}\n")
    t01_ai_home_reachable()
    t02_chat_session_reachable()
    chunks = get_h5_chunks()
    print(f"[info] 已拉取 chunks，总字节: {len(chunks)}\n")
    t03_template_text_present(chunks)
    t04_svg_arrow_path_present(chunks)
    t05_padding_radius_present(chunks)
    t06_font_size_line_height_present(chunks)
    t07_data_is_self_attr_present(chunks)
    t08_prd448_v11_marker(chunks)
    t09_no_legacy_arrow_chars(chunks)
    t10_no_my_archive_placeholder(chunks)
    t11_no_loading_placeholder_in_capsule(chunks)
    t12_ai_home_config_api_ok()

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n==== 结果汇总: {passed}/{total} 通过 ====")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
