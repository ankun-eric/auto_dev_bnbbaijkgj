"""Health check for all service URLs."""
import requests
import urllib3
urllib3.disable_warnings()

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"

urls = [
    ("API 健康检查", f"{BASE_URL}/api/health"),
    ("公告用户端接口", f"{BASE_URL}/api/notices/active"),
    ("API 文档", f"{BASE_URL}/api/docs"),
    ("H5 首页", f"{BASE_URL}/"),
    ("Admin 后台", f"{BASE_URL}/admin/"),
]

all_ok = True
for name, url in urls:
    try:
        resp = requests.get(url, verify=False, timeout=15, allow_redirects=True)
        ok = resp.status_code < 400
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: HTTP {resp.status_code} - {url}")
        if not ok:
            all_ok = False
    except Exception as e:
        print(f"  [ERROR] {name}: {e} - {url}")
        all_ok = False

print(f"\n健康检查结果: {'全部通过' if all_ok else '存在失败项'}")
