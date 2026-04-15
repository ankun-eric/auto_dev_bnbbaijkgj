import requests

base = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

urls = [
    (f"{base}/", "H5 首页"),
    (f"{base}/login/", "H5 登录页"),
    (f"{base}/admin/", "Admin 管理后台"),
    (f"{base}/admin/login/", "Admin 登录页"),
    (f"{base}/api/health", "API 健康检查"),
    (f"{base}/api/settings/logo", "LOGO获取API(新)"),
    (f"{base}/api/register-settings", "注册设置API"),
]

for url, desc in urls:
    try:
        r = requests.get(url, timeout=15, allow_redirects=True, verify=False)
        status = r.status_code
        ok = "PASS" if status == 200 else "FAIL"
        print(f"[{ok}] {status} - {desc}: {url}")
    except Exception as e:
        print(f"[FAIL] ERR - {desc}: {url} -> {e}")
