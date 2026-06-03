"""数字安全绳 v1 修复 - 13 项端到端冒烟核查脚本（部署后必通过）"""
import urllib.request, urllib.error, json, ssl, sys, re

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def http(method, path, headers=None, body=None, follow=True):
    if path.startswith("http"):
        url = path
    elif path.startswith("/autodev/"):
        # 已含基础 path 前缀，使用域名
        url = "https://newbb.test.bangbangvip.com" + path
    elif path.startswith("/"):
        url = BASE + path
    else:
        url = path
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"} if body is not None else {}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=25) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, f"NETERR:{e}"


def get(path, **kw):
    return http("GET", path, **kw)


def post(path, body=None, **kw):
    return http("POST", path, body=body or {}, **kw)


PASS = "PASS"
FAIL = "FAIL"

results = []


def check(idx, name, ok, detail=""):
    tag = PASS if ok else FAIL
    results.append((idx, name, tag, detail))
    print(f"[{idx}] {tag} {name}{(' :: ' + detail) if detail else ''}")


# 先用 GET 抓 care-home 完整页面（要 follow 308 重定向到 /care-home/）
def get_html(path):
    return http("GET", path)


# 1. /care-home 页面 HTML 包含 care-home-safety-rope-entry
sc, body = get_html("/care-home/")
check(1, "/care-home 页面含 care-home-safety-rope-entry 卡片",
      sc == 200 and "care-home-safety-rope-entry" in body, f"HTTP {sc}")

# 2. /care-home 页面 HTML 包含 care-home-safety-rope-fab 悬浮球
check(2, "/care-home 页面含 care-home-safety-rope-fab 悬浮球",
      sc == 200 and "care-home-safety-rope-fab" in body, f"HTTP {sc}")

# 3. /care-home 页面文本含 "数字安全绳"
check(3, "/care-home 页面含 数字安全绳 4 字",
      sc == 200 and ("数字安全绳" in body), f"HTTP {sc}")

# /care-safety-rope 是 'use client' 组件，关键字符串在 JS chunk 中
# 先抓 HTML 提取 chunk URL，再下载 chunk 检查
sc2, body2 = get_html("/care-safety-rope/")
chunk_match = re.search(r'(/autodev/[^"\']+/_next/static/chunks/app/care-safety-rope/[^"\']+\.js)', body2)
chunk_text = ""
if chunk_match:
    chunk_url = chunk_match.group(1)
    sc2c, chunk_text = get_html(chunk_url)
else:
    sc2c = 0


# 4. JS chunk 含 sr-threshold-
check(4, "/care-safety-rope 页面 JS chunk 含 sr-threshold- 标识",
      sc2 == 200 and chunk_match is not None and "sr-threshold-" in chunk_text,
      f"HTTP {sc2}/chunk {sc2c}")

# 5. JS chunk 含 24/48 阈值
check(5, "/care-safety-rope JS chunk 含 阈值 24/48 + sr-threshold-",
      sc2 == 200 and "sr-threshold-" in chunk_text and "24" in chunk_text and "48" in chunk_text,
      f"HTTP {sc2}")

# 6-11. 后端 API 路由可达（无 token 时应返回 401，不能是 404）
def api_alive(path, method="GET", body=None):
    sc, _ = http(method, path, body=body if method != "GET" else None)
    return sc, sc not in (0, 404)


api_targets = [
    (6, "GET /api/safety-rope/status",          "/api/safety-rope/status",                "GET",  None),
    (7, "PUT /api/safety-rope/config",          "/api/safety-rope/config",                "PUT",  {"threshold_hours": 48}),
    (8, "GET /api/safety-rope/contacts",        "/api/safety-rope/contacts",              "GET",  None),
    (9, "GET /api/safety-rope/contacts/check-phone","/api/safety-rope/contacts/check-phone?phone=13800138000","GET",None),
    (10,"POST /api/safety-rope/checkin",        "/api/safety-rope/checkin",               "POST", {}),
    (11,"POST /api/safety-rope/contacts (route)","/api/safety-rope/contacts",             "POST", {"name":"x","phone":"13800138000"}),
]

for idx, name, p, m, b in api_targets:
    sc, alive = api_alive(p, m, b)
    check(idx, name + f" (期望 ≠ 404)", alive, f"HTTP {sc}")

# 12. OpenAPI 含 safety_rope_v1 标签
sc12, body12 = get("/api/openapi.json")
has_tag = False
if sc12 == 200:
    try:
        j = json.loads(body12)
        # 检查 paths 里是否含 safety-rope
        paths = j.get("paths", {})
        sr_paths = [p for p in paths if "safety-rope" in p]
        # 检查 tag 名
        tags_in_paths = set()
        for p in sr_paths:
            for m in paths[p].values():
                if isinstance(m, dict):
                    for t in m.get("tags", []) or []:
                        tags_in_paths.add(t)
        has_tag = len(sr_paths) >= 6 and ("数字安全绳" in tags_in_paths or any("safety_rope" in t.lower() or "safety-rope" in t.lower() for t in tags_in_paths))
    except Exception:
        pass
check(12, "OpenAPI 含 safety_rope_v1 (≥6 个路径 + tag)",
      has_tag, f"HTTP {sc12}")

# 13. 关系字段 7 芯片单选已落地（chunk 中）
chips = ["子女", "配偶", "父母", "邻居", "朋友", "护工", "其他"]
all_in_chunk = chunk_text and all(c in chunk_text for c in chips)
check(13, "关系 7 芯片（子女/配偶/父母/邻居/朋友/护工/其他）落地 JS chunk",
      bool(all_in_chunk), f"chunk_len={len(chunk_text)}")

print()
total = len(results)
passed = sum(1 for r in results if r[2] == PASS)
print(f"==== SUMMARY: {passed}/{total} PASSED ====")
if passed != total:
    failed = [(r[0], r[1], r[3]) for r in results if r[2] == FAIL]
    for f in failed:
        print(f"  - [{f[0]}] {f[1]} :: {f[2]}")
    sys.exit(1)
sys.exit(0)
