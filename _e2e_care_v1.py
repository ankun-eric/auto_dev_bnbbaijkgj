"""E2E 测试：直接打服务器 HTTPS API"""
import json
import urllib.request
import urllib.error
import ssl

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
ctx = ssl.create_default_context()


def call(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


tests = []


def expect(name, actual, expected):
    ok = actual == expected
    tests.append((name, ok, actual, expected))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: actual={actual} expected={expected}")


# 1) keywords
code, body = call("GET", "/api/care-v1/sos/keywords")
expect("AC18 关键词配置接口可访问", code, 200)
expect("AC18 包含 4 个分类", set(body["data"].keys()), {"high_risk", "symptom", "degree", "negation"})
expect("AC18 默认含 '救命'", "救命" in body["data"]["high_risk"], True)

# 2) detect 高危词
code, body = call("POST", "/api/care-v1/sos/detect", {"text": "救命"})
expect("AC11 高危词触发", code, 200)
expect("AC11 hit=True", body["data"]["hit"], True)
expect("AC11 rule=high_risk", body["data"]["rule"], "high_risk")

# 3) detect 双词触发
code, body = call("POST", "/api/care-v1/sos/detect", {"text": "胸闷得厉害"})
expect("AC12 双词触发 hit", body["data"]["hit"], True)
expect("AC12 rule=combo", body["data"]["rule"], "combo")

# 4) 否定词过滤
code, body = call("POST", "/api/care-v1/sos/detect", {"text": "胸口不闷"})
expect("AC13 否定过滤", body["data"]["hit"], False)

# 5) 疑问句过滤
code, body = call("POST", "/api/care-v1/sos/detect", {"text": "是不是要胸闷？"})
expect("AC14 疑问过滤", body["data"]["hit"], False)

# 6) 单独症状词不触发
code, body = call("POST", "/api/care-v1/sos/detect", {"text": "今天有点头晕"})
expect("规则3 单独症状不触发", body["data"]["hit"], False)

# 7) 未登录访问 /user-preferences 应该 401
code, body = call("GET", "/api/care-v1/user-preferences")
expect("未登录被拒绝", code, 401)

# 8) welcome-mode 页面
data = urllib.request.urlopen(BASE + "/welcome-mode/", context=ctx, timeout=20).read().decode("utf-8")
expect("welcome-mode 页含 '关怀模式'", "关怀模式" in data, True)
expect("welcome-mode 页含 '标准模式'", "标准模式" in data, True)

# 9) care-home 页面
data = urllib.request.urlopen(BASE + "/care-home/", context=ctx, timeout=20).read().decode("utf-8")
expect("care-home 页含 'SOS'", "SOS" in data, True)
expect("care-home 页含 '宾尼小康'", "宾尼小康" in data, True)

passed = sum(1 for _, ok, *_ in tests if ok)
total = len(tests)
print(f"\n=== Total: {passed}/{total} passed ===")
if passed < total:
    print("FAILED tests:")
    for n, ok, a, e in tests:
        if not ok:
            print(f"  {n}: actual={a} expected={e}")
    exit(1)
