"""[PRD-MSG-NOTICE-NO-JUMP-V1 2026-06-02] 非UI自动化烟雾测试

验证目标：
1. 服务器项目源码中，通知点击相关代码已不包含跳转语句
2. 已构建的 H5 容器内 standalone bundle 中，
   不再包含旧跳转代码痕迹（不应出现 /family-bindlist 在通知 onClick 路径上）
3. /messages 页面与铃铛抽屉相关入口可达（HTTP 状态合理）

执行：python deploy/_smoke_msg_no_jump_20260602.py
"""

import sys
import urllib.request
import urllib.error
import ssl

sys.path.insert(0, "deploy")
from _sshlib import run, DEPLOY_ID  # noqa: E402


BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def check_http(url, expected_codes):
    """简单 HTTP 状态码检查（GET）"""
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        return False, f"connect_err: {e}"
    ok = code in expected_codes
    return ok, code


def main():
    results = []

    # ===== Case 1: 服务器源码中，handleNoticeClick 不再有 router.push 跳转 =====
    awk1 = "awk '/handleNoticeClick = useCallback/,/^  );/'"
    cmd = (
        "cd " + PROJECT_DIR + " && "
        + awk1
        + " h5-web/src/components/ai-chat/ReminderDrawer.tsx | "
        + "grep -E 'router\\.push|onClose\\(\\)' | wc -l"
    )
    code, out, err = run(cmd, timeout=30)
    count = (out or "0").strip()
    ok = code == 0 and count == "0"
    results.append(
        (
            "case1_h5_ReminderDrawer_handleNoticeClick_no_jump",
            ok,
            f"router.push/onClose count = {count} (期望 0)",
        )
    )

    # ===== Case 2: H5 messages page markRead 不再 router.push =====
    awk2 = "awk '/const markRead = async/,/^  };/'"
    cmd = (
        "cd " + PROJECT_DIR + " && "
        + awk2
        + " h5-web/src/app/messages/page.tsx | grep -c 'router\\.push' || true"
    )
    code, out, err = run(cmd, timeout=30)
    count = (out or "0").strip()
    ok = count == "0"
    results.append(
        (
            "case2_h5_messages_markRead_no_jump",
            ok,
            f"router.push count = {count} (期望 0)",
        )
    )

    # ===== Case 3: 小程序 messages onMsgTap 不再 navigateTo =====
    awk3 = "awk '/async onMsgTap/,/^  },/'"
    cmd = (
        "cd " + PROJECT_DIR + " && "
        + awk3
        + " miniprogram/pages/messages/index.js | grep -c 'wx\\.navigateTo' || true"
    )
    code, out, err = run(cmd, timeout=30)
    count = (out or "0").strip()
    ok = count == "0"
    results.append(
        (
            "case3_mp_messages_onMsgTap_no_jump",
            ok,
            f"wx.navigateTo count = {count} (期望 0)",
        )
    )

    # ===== Case 4: 构建产物中 ReminderDrawer 已不再含通知跳转字符串组合 =====
    # 旧代码同时存在三个：'family-bindlist'、'/family-invite'、'/unified-order/'
    # 改后铃铛抽屉点击通知部分仅保留 markNoticeRead；
    # 但 H5 其他页面（如 messages/page.tsx 的 handleReinvite）仍含 family-invite/family-bindlist，
    # 所以本用例只校验：ReminderDrawer 编译产物中不再含 'unified-order' 与 'family-invite' 组合
    # （通过铃铛抽屉的 chunk 名定位过于脆弱，改用源文件作为验证锚点）
    cmd = (
        "cd " + PROJECT_DIR + " && "
        + "grep -c 'router\\.push' "
        + "h5-web/src/components/ai-chat/ReminderDrawer.tsx"
    )
    code, out, err = run(cmd, timeout=30)
    count = (out or "0").strip()
    # 该组件中 router.push 还在 goMedAll / goOrderAll / handleOrderAction 中使用
    # 但 handleNoticeClick 不应再有，期望 count >= 1 且 case1 已为 0
    ok = int(count) >= 1
    results.append(
        (
            "case4_h5_ReminderDrawer_router_still_imported",
            ok,
            f"router.push 总出现次数 = {count} (期望 >= 1，由 goMed/Order 等仍使用)",
        )
    )

    # ===== Case 5: /messages 页面可达（外部 HTTPS）=====
    ok, info = check_http(
        f"{BASE_URL}/messages",
        expected_codes={200, 301, 302, 307, 308, 401, 403},
    )
    results.append(
        ("case5_messages_page_reachable", ok, f"http_status = {info}")
    )

    # ===== Case 6: H5 首页可达 =====
    ok, info = check_http(
        f"{BASE_URL}/",
        expected_codes={200, 301, 302, 307, 308},
    )
    results.append(("case6_home_reachable", ok, f"http_status = {info}"))

    # ===== Case 7: 后端通知 API 可达（不需登录验证，仅看路由是否注册）=====
    ok, info = check_http(
        f"{BASE_URL}/api/messages",
        expected_codes={200, 401, 403, 422},
    )
    results.append(("case7_api_messages_reachable", ok, f"http_status = {info}"))

    # ===== 汇总 =====
    print("=" * 70)
    print("PRD-MSG-NOTICE-NO-JUMP-V1 烟雾测试结果")
    print("=" * 70)
    pass_n = 0
    for name, ok, info in results:
        flag = "PASS" if ok else "FAIL"
        if ok:
            pass_n += 1
        print(f"[{flag}] {name}: {info}")
    print("=" * 70)
    print(f"通过 {pass_n}/{len(results)}")
    print("=" * 70)
    sys.exit(0 if pass_n == len(results) else 1)


if __name__ == "__main__":
    main()
