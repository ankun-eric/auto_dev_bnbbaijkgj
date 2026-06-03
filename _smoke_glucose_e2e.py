"""[GLUCOSE-V1] 远程服务器 E2E smoke：注册 → 登录 → 录入 → 拉列表/统计/AI/报告/提醒。"""
import json
import random
import time
import urllib.request
import urllib.error

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"


def http(method, path, body=None, token=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "Client-Type": "h5-user"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


phone = f"139{random.randint(10000000, 99999999)}"

# 注册
code, _ = http("POST", "/api/auth/register",
               {"phone": phone, "password": "user123", "nickname": "血糖SMK"})
print("register:", code)

# 登录
code, body = http("POST", "/api/auth/login", {"phone": phone, "password": "user123"})
print("login:", code)
token = body.get("access_token")
assert token, body

# 录入正常
code, body = http("POST", "/api/glucose-v1/records",
                  {"value": 5.5, "scene": 1}, token=token)
print("create_normal:", code, body.get("record", {}).get("level_label"),
      "alert:", body.get("alert"))
assert code == 200 and body["record"]["level"] == 3 and body["alert"] is None

# 录入高糖危象
code, body = http("POST", "/api/glucose-v1/records",
                  {"value": 18.5, "scene": 2}, token=token)
print("create_crisis:", code, body.get("record", {}).get("crisis_label"),
      "must_popup:", body.get("alert", {}).get("must_popup"))
assert code == 200 and body["record"]["is_crisis"] == 1
assert body["alert"]["must_popup"] is True

# 录入低糖危象
code, body = http("POST", "/api/glucose-v1/records",
                  {"value": 2.3, "scene": 3}, token=token)
print("create_low_crisis:", code, body.get("record", {}).get("crisis_label"))
assert code == 200 and body["record"]["is_crisis"] == 2

# 录入超范围
code, body = http("POST", "/api/glucose-v1/records",
                  {"value": 40.0, "scene": 1}, token=token)
print("create_out_of_range:", code, body.get("detail"))
assert code == 400

# 列表
code, body = http("GET", "/api/glucose-v1/records?days=7&size=20", token=token)
print("list:", code, "total:", body.get("total"))
assert code == 200 and body["total"] >= 3

# 统计
code, body = http("GET", "/api/glucose-v1/stats?days=7", token=token)
print("stats:", code, "count:", body.get("count"), "abnormal:", body.get("abnormal_count"))
assert code == 200 and body["count"] >= 3

# 预警
code, body = http("GET", "/api/glucose-v1/alerts?days=30", token=token)
print("alerts:", code, "total:", body.get("total"))
assert code == 200 and body["total"] >= 2

# AI 建议
code, body = http("GET", "/api/glucose-v1/ai-advice?days=30", token=token)
print("ai-advice:", code, "disclaimer:", body.get("disclaimer", "")[:20])
assert code == 200 and "仅供参考" in body["disclaimer"]

# 报告
code, body = http("GET", "/api/glucose-v1/report?days=30", token=token)
print("report:", code, "share_valid_days:", body.get("share_valid_days"))
assert code == 200

# 提醒配置
code, body = http("PUT", "/api/glucose-v1/reminder",
                  {"breakfast": "07:00", "lunch": "12:00", "dinner": "18:30",
                   "enabled": True}, token=token)
print("reminder_set:", code, body)
assert code == 200

code, body = http("GET", "/api/glucose-v1/reminder", token=token)
print("reminder_get:", code, body)
assert code == 200 and body["enabled"] is True

# 前端页面访问
import ssl
ctx = ssl.create_default_context()
req = urllib.request.Request(f"{BASE}/glucose", method="GET")
with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
    page_status = r.status
    page_body = r.read().decode("utf-8", errors="ignore")
print("glucose page:", page_status, "has-tabs:", "glucose-tabs" in page_body)

print("\n✅ ALL E2E SMOKE PASSED")
