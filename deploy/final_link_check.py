"""最终链接可达性验证"""
import urllib.request, urllib.error, ssl, json
BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
ctx = ssl.create_default_context()

LINKS = [
    ("H5 首页",            f"{BASE}/"),
    ("H5 我的",            f"{BASE}/profile"),
    ("H5 我的积分",        f"{BASE}/points"),
    ("H5 积分明细",        f"{BASE}/points/records"),
    ("H5 AI 健康咨询",     f"{BASE}/ai"),
    ("H5 健康档案编辑",    f"{BASE}/profile/edit"),
    ("H5 服务列表",        f"{BASE}/services"),
    ("H5 我的订单",        f"{BASE}/unified-orders"),
    ("H5 健康计划",        f"{BASE}/health-plan"),
    ("Admin 后台",         f"{BASE}/admin/"),
    ("API home-config",    f"{BASE}/api/home-config"),
    ("API health",         f"{BASE}/api/health"),
    ("APK",                f"{BASE}/apk/bini_health.apk"),
    ("MP latest",          f"{BASE}/downloads/miniprogram_latest.zip"),
    ("MP bugfix7",         f"{BASE}/downloads/miniprogram_bugfix7_1776649904.zip"),
]

print(f"{'STATUS':>7} {'NAME':<22} URL")
print("-"*100)
ok = 0
for name, url in LINKS:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent":"Mozilla/5.0"})
        r = urllib.request.urlopen(req, timeout=20, context=ctx)
        code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:
        code = f"ERR:{type(e).__name__}"
    flag = "OK" if str(code) in ("200","301","302","307","308") else "!!"
    if flag == "OK": ok += 1
    print(f"{flag:>3}{code:>4} {name:<22} {url}")

print(f"\n[*] PASSED: {ok}/{len(LINKS)}")
