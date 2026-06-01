import urllib.request, ssl, sys

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
ctx = ssl.create_default_context()

def fetch(path):
    url = BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": "smoke/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore") if e.fp else ""
    except Exception as e:
        return -1, str(e)

# Routes to verify reachable (related + key)
routes = [
    "/ai-home",
    "/care-ai-home",
    "/health-profile",
    "/services",
    "/invite",
    "/feedback",
    "/member-center",
]

print("=== 链接可达性 ===")
ok = True
results = {}
for r in routes:
    st, body = fetch(r)
    results[r] = (st, body)
    flag = "OK" if st in (200, 405) else "FAIL"
    if st not in (200, 405):
        ok = False
    print(f"[{flag}] {st}  {r}")

print("\n=== 关怀版顶栏统一 (care-ai-home) ===")
_, care = results["/care-ai-home"]
care_checks = {
    "顶栏三Tab容器 care-home-top-tabs": "care-home-top-tabs" in care,
    "档案Tab": "care-home-top-tab-profile" in care,
    "咨询Tab": "care-home-top-tab-consult" in care,
    "服务Tab": "care-home-top-tab-service" in care,
    "铃铛 care-home-topbar-bell": "care-home-topbar-bell" in care,
    "加号圈 plus-circle": "care-home-more-icon-plus-circle" in care,
    "欢迎区胶囊 care-home-mode-capsule": "care-home-mode-capsule" in care,
    "胶囊文案=关怀版": "关怀版" in care,
    "[移除] 宾尼小康 模式切换 已不在": "宾尼小康 模式切换" not in care,
}
for k, v in care_checks.items():
    if not v: ok = False
    print(f"[{'OK' if v else 'FAIL'}] {k}")

print("\n=== 标准版欢迎区胶囊 (ai-home) ===")
_, home = results["/ai-home"]
home_checks = {
    "欢迎区胶囊 ai-home-mode-capsule": "ai-home-mode-capsule" in home,
    "胶囊文案=标准版": "标准版" in home,
    "顶栏三Tab ai-home-top-tabs": "ai-home-top-tabs" in home,
    "加号圈 ai-home-more-btn": "ai-home-more-btn" in home,
}
for k, v in home_checks.items():
    if not v: ok = False
    print(f"[{'OK' if v else 'FAIL'}] {k}")

print("\n=== 总结 ===")
print("ALL PASS" if ok else "HAS FAIL")
sys.exit(0 if ok else 1)
