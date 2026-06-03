"""
[BUG_FIX_H5_GLOBAL_CRASH_20260528] 全站 13 项 checklist HTTP 烟雾测试
验证 H5 修复后所有页面是否可正常访问（HTTP 200 且页面正常 SSR）。
"""
import sys
import urllib.request
import urllib.error
import ssl

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

PAGES = [
    ("首页", f"{BASE}/"),
    ("AI 主页", f"{BASE}/ai-home"),
    ("AI 健康自查（symptom）", f"{BASE}/symptom"),
    ("体质测评 TCM", f"{BASE}/tcm"),
    ("AI 问答（chat-history）", f"{BASE}/chat-history"),
    ("个人中心 / 我的（profile/edit）", f"{BASE}/profile/edit"),
    ("健康档案", f"{BASE}/health-profile"),
    ("守护人/我守护的人（health-profile/i-guard）", f"{BASE}/health-profile/i-guard"),
    ("家庭成员绑定列表", f"{BASE}/family-bindlist"),
    ("居家安全设备", f"{BASE}/home-safety"),
    ("商城/商品列表", f"{BASE}/products"),
    ("订单列表", f"{BASE}/unified-orders"),
    ("通知/消息", f"{BASE}/notifications"),
    ("管理后台", f"{BASE}/admin/"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def check(name, url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "smoke-h5-fix/1.0"})
        resp = urllib.request.urlopen(req, timeout=30, context=ctx)
        body = resp.read()
        text = body.decode("utf-8", errors="ignore")
        status = resp.status
    except urllib.error.HTTPError as e:
        try:
            text = e.read().decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        status = e.code
    except Exception as e:
        return False, f"REQ_ERR {type(e).__name__}: {e}"

    bad_markers = [
        "Application error: a client-side exception",
        "Internal Server Error",
        "Cannot read properties of undefined",
        "is not a function",
        "(0 , _datetime",
        "TypeError",
    ]
    found = [m for m in bad_markers if m in text]
    ok = (status in (200, 307, 308)) and not found
    msg = f"status={status}"
    if found:
        msg += f" BAD_MARKERS={found}"
    return ok, msg


def main():
    ok_count = 0
    fail = []
    print(f"=== H5 全站 checklist 烟雾测试 ===")
    print(f"BASE: {BASE}\n")
    for name, url in PAGES:
        ok, msg = check(name, url)
        flag = "[OK]" if ok else "[FAIL]"
        line = f"{flag} {name:30s} {url}  -- {msg}"
        print(line)
        if ok:
            ok_count += 1
        else:
            fail.append((name, url, msg))
    print(f"\n=== 结果：{ok_count}/{len(PAGES)} 通过 ===")
    if fail:
        print("失败明细：")
        for n, u, m in fail:
            print(f"  - {n}: {u} -- {m}")
        sys.exit(1)
    print("所有页面均可正常访问，无客户端崩溃标记。")
    sys.exit(0)


if __name__ == "__main__":
    main()
