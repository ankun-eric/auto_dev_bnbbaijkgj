"""[PRD-AI-HOME-V1] 部署后链接可达性验证"""
import urllib.request
import urllib.error
import time

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

# 测试路径表：(path, [acceptable_status_codes])
TESTS = [
    ("/",                       [200]),         # 根路径 → 渲染 splash → 跳 /ai-home
    ("/ai-home/",               [200]),         # AI 主页（应能加载邀请图标）
    ("/services/",              [200]),         # 独立服务页（应有返回按钮 + 全局搜索入口）
    ("/ai-settings/",           [200]),         # 设置页（应包含地址入口）
    ("/invite/",                [200]),         # 邀请页（已存在）
    ("/my-addresses/",          [200]),         # 地址管理页（已存在）
    ("/member-card/",           [200]),         # 会员卡页（含二维码接口）
    ("/search/",                [200]),         # 全局搜索页
    ("/login/",                 [200]),         # 登录页
    ("/home/",                  [200, 301, 308]),  # 旧路由：next.config redirect
    ("/ai/",                    [200, 301, 308]),  # 旧路由：next.config redirect
    ("/checkup/",               [200]),         # 不动的独立页
    ("/drug/",                  [200]),         # 不动的独立页
    ("/notifications/",         [200]),         # 抽屉 → 铃铛
    ("/health-archive/",        [200]),         # 抽屉 → 健康档案
    ("/my-coupons/",            [200]),         # 抽屉 → 优惠券
    ("/my-favorites/",          [200]),         # 抽屉 → 收藏
    ("/points/",                [200]),         # 抽屉 → 积分
    ("/unified-orders/",        [200]),         # 抽屉 → 订单
]


def probe(path, expected_codes):
    url = BASE + path
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "PRD-AI-HOME-VERIFY/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            code = resp.status
            body_head = resp.read(2048).decode("utf-8", errors="replace")
            ok = code in expected_codes
            return ok, code, body_head[:200]
    except urllib.error.HTTPError as e:
        ok = e.code in expected_codes
        return ok, e.code, str(e)[:200]
    except Exception as e:
        return False, -1, str(e)[:200]


def main():
    passed = 0
    failed = []
    for path, codes in TESTS:
        # auto follow redirects in urllib by default; HEAD might not, so use GET
        ok, code, snippet = probe(path, codes)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {code:4} {path:30}   {'(expect: ' + ','.join(map(str, codes)) + ')':<30}")
        if ok:
            passed += 1
        else:
            failed.append((path, code, snippet))
    print()
    print(f"Total: {len(TESTS)} | Passed: {passed} | Failed: {len(failed)}")
    if failed:
        print("\n[Failures]")
        for path, code, snippet in failed:
            print(f"  {path}  (got {code})")
            print(f"    snippet: {snippet}")
        return 1
    print("All routes OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
