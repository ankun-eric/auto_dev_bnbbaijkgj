import json, urllib.request, urllib.error, random

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
API = BASE + "/api"

def req(method, path, body=None, token=None):
    url = API + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    r.add_header("Client-Type", "h5-user")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}

phone = "139" + "".join(random.choice("0123456789") for _ in range(8))
pwd = "test123456"

# 注册（可能已存在）
s, j = req("POST", "/auth/register", {"phone": phone, "password": pwd, "nickname": "统计测试"})
print("register", s)
# 登录
s, j = req("POST", "/auth/login", {"phone": phone, "password": pwd})
print("login", s)
token = j.get("access_token")
assert token, j

# 初始统计（应为空）
s, j = req("GET", "/home_safety/devices", token=token)
print("devices(empty)", s, "total_bound=", j.get("total_bound"), "type_counts=", j.get("type_counts"))
assert s == 200
assert j.get("total_bound") == 0, j
assert j.get("type_counts") == {"emergency":0,"smoke":0,"water":0}, j

def rid(n):
    import random,string
    return "".join(random.choice(string.ascii_uppercase+string.digits) for _ in range(n))

# 绑定 1 紧急 + 1 烟雾
for dt in (1, 2):
    body = {"device_type": dt, "gateway_sn": rid(8), "device_sn": rid(8),
            "emergency_phone": "13800001234", "remark": "测试设备"}
    s, j = req("POST", "/home_safety/devices/bind", body, token=token)
    print("bind type", dt, "->", s, j.get("detail") if s != 200 else "ok")
    assert s == 200, j

# 再次统计
s, j = req("GET", "/home_safety/devices", token=token)
print("devices(after)", s, "total_bound=", j.get("total_bound"), "type_counts=", j.get("type_counts"))
assert j.get("total_bound") == 2, j
assert j.get("type_counts") == {"emergency":1,"smoke":1,"water":0}, j

print("\nE2E PASS: 统计字段在线上接口正确返回")
