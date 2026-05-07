"""[PRD-370 BUG-FIX-LOGIN-DESIGN-ALIGN-V1] 非UI自动化验收测试

通过 HTTPS 拉取登录页 HTML + chunk JS 内容，做正向/反向关键词扫描，验证：
- 主色 #34C759 / 浅绿 #4AD97A / 青色尾段 #2BD4C4
- 主标题"宾尼小康"、副标题"AI 健康管家"
- 删除"欢迎回来"等冗余问候语
- "服务协议及隐私保护"协议确认弹窗文案
- "不同意"/"同意"双按钮
- legal 路由可达 + 远程开关接口可达
"""
from __future__ import annotations
import re
import ssl
import sys
import urllib.request
import urllib.error
import json

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def fetch(url: str, timeout: int = 20) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 PRD370-Verify",
            "Accept": "text/html,application/json,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return -1, f"ERR: {e}"


def to_unicode_escape(s: str) -> str:
    """把中文转为 Next.js 打包后可能出现的 \\uXXXX 形式（小写）。"""
    return "".join(f"\\u{ord(c):04x}" for c in s)


def find_chunks(html: str) -> list[str]:
    paths = re.findall(r'(?:/autodev/[a-f0-9-]+)?/_next/static/chunks/app/login/[a-zA-Z0-9_\-./]+\.js', html)
    paths += re.findall(r'(?:/autodev/[a-f0-9-]+)?/_next/static/chunks/[a-zA-Z0-9_\-./]+\.js', html)
    return list(dict.fromkeys(paths))


def to_full_url(path: str) -> str:
    """把相对路径修正为以 BASE 为根的完整 URL（chunk 路径若已包含 /autodev/{id} 则原样使用）。"""
    if path.startswith("http"):
        return path
    if "/autodev/" in path:
        return f"https://newbb.test.bangbangvip.com{path}"
    # path 形如 /_next/... → 加上项目 base
    return f"{BASE}{path}"


cases: list[tuple[str, bool, str]] = []  # (name, passed, msg)


def case(name: str, passed: bool, msg: str = "") -> None:
    cases.append((name, passed, msg))
    flag = "PASS" if passed else "FAIL"
    print(f"[{flag}] {name}  {msg}")


# === 1. 登录页可达 ===
status, html = fetch(f"{BASE}/login/")
case("TC-1.1 登录页 HTTP 200", status == 200, f"status={status}")
case("TC-1.2 登录页 HTML 非空", len(html) > 1000, f"len={len(html)}")

# === 2. 抓取 login chunk 并下载 ===
chunk_paths = find_chunks(html)
login_chunk_paths = [p for p in chunk_paths if "/app/login/" in p]
case("TC-2.1 login chunk 提取成功", len(login_chunk_paths) > 0, f"chunks={login_chunk_paths}")

login_chunk_content = ""
if login_chunk_paths:
    chunk_url = to_full_url(login_chunk_paths[0])
    cstatus, login_chunk_content = fetch(chunk_url)
    case("TC-2.2 login chunk 下载成功",
         cstatus == 200 and len(login_chunk_content) > 1000,
         f"url={chunk_url}, status={cstatus}, len={len(login_chunk_content)}")

# === 3. 主色 / 渐变色 token 验证 ===
case("TC-3.1 主色 #34C759 出现", "34C759" in login_chunk_content, "iOS 标准绿")
case("TC-3.2 浅绿 #4AD97A 出现", "4AD97A" in login_chunk_content, "渐变起点")
# 三段渐变尾段 #2BD4C4 在 CSS module 中（被 Next.js 提取到独立 .css），同时检查页面 HTML 引用的 CSS
css_paths = re.findall(r'(?:/autodev/[a-f0-9-]+)?/_next/static/css/[a-zA-Z0-9_\-./]+\.css', html)
css_paths = list(dict.fromkeys(css_paths))
css_combined = ""
for p in css_paths[:3]:
    s, body = fetch(to_full_url(p))
    if s == 200:
        css_combined += body
case("TC-3.3 青色 #2BD4C4 出现（chunk JS 或 CSS）",
     "2BD4C4" in login_chunk_content or "2bd4c4" in login_chunk_content
     or "2BD4C4" in css_combined or "2bd4c4" in css_combined,
     f"css_files={len(css_paths)}, css_total_len={len(css_combined)}")

# === 4. 文案：宾尼小康 / AI 健康管家 ===
title_uesc = to_unicode_escape("宾尼小康")
sub_uesc = to_unicode_escape("AI 健康管家")

case("TC-4.1 主标题'宾尼小康'存在",
     title_uesc in login_chunk_content or "宾尼小康" in login_chunk_content,
     f"esc={title_uesc}")
case("TC-4.2 副标题'AI 健康管家'存在",
     sub_uesc in login_chunk_content or "AI 健康管家" in login_chunk_content,
     "")

# === 5. 反向校验：删除冗余问候语 ===
welcome_uesc = to_unicode_escape("欢迎回来")
case("TC-5.1 卡片不再出现'欢迎回来'",
     welcome_uesc not in login_chunk_content and "欢迎回来" not in login_chunk_content,
     "")

oneclick_uesc = to_unicode_escape("手机号一键登录")
case("TC-5.2 卡片不再出现'手机号一键登录'",
     oneclick_uesc not in login_chunk_content and "手机号一键登录" not in login_chunk_content,
     "")

# === 6. 协议二次确认弹窗 ===
dialog_title_uesc = to_unicode_escape("服务协议及隐私保护")
case("TC-6.1 弹窗标题'服务协议及隐私保护'",
     dialog_title_uesc in login_chunk_content or "服务协议及隐私保护" in login_chunk_content,
     "")

reject_uesc = to_unicode_escape("不同意")
case("TC-6.2 弹窗按钮'不同意'",
     reject_uesc in login_chunk_content or "不同意" in login_chunk_content,
     "")

agree_uesc = to_unicode_escape("同意")
case("TC-6.3 弹窗按钮'同意'存在",
     agree_uesc in login_chunk_content or "同意" in login_chunk_content,
     "")

# === 7. 协议详情路由 ===
sa_status, sa_body = fetch(f"{BASE}/legal/service-agreement/")
case("TC-7.1 /legal/service-agreement/ 可访问",
     sa_status == 200,
     f"status={sa_status}")
case("TC-7.2 用户服务协议页面含协议正文",
     "用户服务协议" in sa_body or to_unicode_escape("用户服务协议") in sa_body,
     "")

pp_status, pp_body = fetch(f"{BASE}/legal/privacy-policy/")
case("TC-7.3 /legal/privacy-policy/ 可访问",
     pp_status == 200,
     f"status={pp_status}")
case("TC-7.4 隐私政策页面含正文",
     "隐私政策" in pp_body or to_unicode_escape("隐私政策") in pp_body,
     "")

# === 8. 后端远程开关 ===
sw_status, sw_body = fetch(f"{BASE}/api/config/login_ui_version")
case("TC-8.1 /api/config/login_ui_version 可达", sw_status == 200, f"status={sw_status}")
try:
    sw_data = json.loads(sw_body)
    case("TC-8.2 远程开关返回 version 字段",
         "version" in sw_data,
         f"version={sw_data.get('version')}")
    case("TC-8.3 远程开关默认 v2",
         sw_data.get("version") == "v2",
         f"version={sw_data.get('version')}")
    case("TC-8.4 远程开关 rollback_supported=true",
         sw_data.get("rollback_supported") is True,
         "")
except Exception as e:
    case("TC-8.2 远程开关返回 JSON", False, f"err={e}")

# === 9. /api/auth/register-settings 可达 ===
rs_status, rs_body = fetch(f"{BASE}/api/auth/register-settings")
case("TC-9.1 /api/auth/register-settings 可达",
     rs_status in (200, 401, 403),
     f"status={rs_status}")

# === 10. theme-color 已更新 ===
case("TC-10 layout theme-color 含 #34C759",
     "#34C759" in html or "34C759" in html,
     "")

# === 汇总 ===
total = len(cases)
passed = sum(1 for _, p, _ in cases if p)
print(f"\n=== PRD-370 验收汇总: {passed}/{total} 通过 ===")
for name, p, msg in cases:
    if not p:
        print(f"  FAIL  {name}  {msg}")

sys.exit(0 if passed == total else 2)
