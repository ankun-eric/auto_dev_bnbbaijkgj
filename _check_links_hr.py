"""外部链接可达性检查（真实 HTTPS）。"""
import urllib.request, ssl

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
ctx = ssl.create_default_context()

# 前端页面 + 后端 API（GET 可达性）
links = [
    ("前端首页", f"{BASE}/", None),
    ("心率详情页", f"{BASE}/health-metric/heart_rate?profileId=1", None),
    ("血压详情页", f"{BASE}/health-metric/blood_pressure?profileId=1", None),
    ("健康指标meta API", f"{BASE}/api/health-metric-v1/meta", None),
    ("后端健康检查", f"{BASE}/api/health", None),
]

ok = 0
for name, url, _ in links:
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "smoke/1.0"})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            code = resp.status
        result = "OK" if code < 400 or code == 405 else "FAIL"
    except urllib.error.HTTPError as e:
        code = e.code
        result = "OK" if code in (401, 403, 405, 422) else "FAIL"  # 需鉴权/方法不符也算可达
    except Exception as e:
        code = f"ERR:{e}"
        result = "FAIL"
    if result == "OK":
        ok += 1
    print(f"[{result}] {code}  {name}  {url}")

print(f"\n可达 {ok}/{len(links)}")
