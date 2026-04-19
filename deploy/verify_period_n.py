"""验证第 N 期所有 BUG 修复 + 改造 ④ 在线效果。"""
import urllib.request
import ssl
import json
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
ctx = ssl.create_default_context()


def fetch(path, method="GET", headers=None, data=None):
    req = urllib.request.Request(BASE + path, method=method, headers=headers or {}, data=data)
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            body = r.read()
            return r.status, dict(r.headers), body
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except Exception as e:
        return -1, {}, str(e).encode()


print("=" * 60)
print("【BUG ②】Logo 绝对 URL")
print("=" * 60)
status, hdr, body = fetch("/api/settings/logo")
print(f"  {status} {body[:200].decode('utf-8', 'replace')}")
data = json.loads(body)
logo_url = data.get("data", {}).get("logo_url")
if logo_url:
    print(f"  Logo 实际可访问性测试 → {logo_url}")
    s2, h2, _ = fetch(logo_url.replace(BASE, ""))
    print(f"  Logo 文件 HTTP {s2}, Content-Type={h2.get('Content-Type')}")
    print(f"  Cache-Control={h2.get('Cache-Control')}, Expires={h2.get('Expires')}")

print()
print("=" * 60)
print("【BUG ⑤】「适老化改造」必须是「居家服务」的子类")
print("=" * 60)
status, _, body = fetch("/api/products/categories")
data = json.loads(body)
items = data.get("items", [])
top_names = [c["name"] for c in items]
print(f"  顶级分类列表: {top_names}")
home = next((c for c in items if c["name"] == "居家服务"), None)
elderly_top = "适老化改造" in top_names
elderly_under_home = home and any(ch["name"] == "适老化改造" for ch in home.get("children", []))
print(f"  适老化改造在顶级? {elderly_top}（应为 False）")
print(f"  适老化改造在居家服务下? {elderly_under_home}（应为 True）")

print()
print("=" * 60)
print("【改造 ④】hot-recommendations 接口")
print("=" * 60)
status, _, body = fetch("/api/products/hot-recommendations?limit=6")
data = json.loads(body)
items = data.get("items", [])
print(f"  HTTP {status}, 返回 {len(items)} 个商品")
for p in items[:3]:
    print(f"    - {p.get('name')} | fulfillment_type={p.get('fulfillment_type')}")

print()
print("=" * 60)
print("【改造 ④】list_products 支持 parent_category_id")
print("=" * 60)
home_id = home["id"] if home else 2
status, _, body = fetch(f"/api/products?parent_category_id={home_id}")
data = json.loads(body)
print(f"  HTTP {status}, 居家服务大类下商品数 = {data.get('total', 0)}")

print()
print("=" * 60)
print("【改造 ④】关键词搜索 q 参数")
print("=" * 60)
import urllib.parse as _up
status, _, body = fetch(f"/api/products?q={_up.quote('测试')}")
print(f"  HTTP {status}")
try:
    data = json.loads(body)
    print(f"  搜索「测试」匹配 = {data.get('total', 0)}")
except Exception as e:
    print(f"  parse err: {e}; body[:200]={body[:200]}")

print()
print("=" * 60)
print("【BUG ③】管理后台 CSV 导出（无 token 验证 401，有 token 验证 CSV）")
print("=" * 60)
# 先登录
import urllib.parse
login_data = json.dumps({"phone": "13800000000", "password": "admin123"}).encode()
status, _, body = fetch("/api/admin/login", method="POST",
                         headers={"Content-Type": "application/json"}, data=login_data)
print(f"  admin login → {status}")
if status == 200:
    token = json.loads(body).get("token")
    # 找一个 batch
    s2, _, b2 = fetch("/api/admin/coupons/redeem-code-batches?page=1&page_size=5",
                       headers={"Authorization": f"Bearer {token}"})
    if s2 == 200:
        bd = json.loads(b2)
        bs = bd.get("items", [])
        print(f"  现有批次: {len(bs)}")
        if bs:
            bid = bs[0]["id"]
            s3, h3, b3 = fetch(f"/api/admin/coupons/redeem-code-batches/{bid}/codes/export",
                                headers={"Authorization": f"Bearer {token}"})
            print(f"  /codes/export HTTP {s3}, Content-Type={h3.get('Content-Type')}, Content-Disposition={h3.get('Content-Disposition')}")
            print(f"  开头 4 字节 BOM: {b3[:4]} (期望 b'\\xef\\xbb\\xbf,'/code...)")
        # 也测一个不存在 batch
        s4, h4, b4 = fetch("/api/admin/coupons/redeem-code-batches/99999/codes/export",
                            headers={"Authorization": f"Bearer {token}"})
        print(f"  不存在 batch /codes/export HTTP {s4}, CT={h4.get('Content-Type')}")
print()
print("=" * 60)
print("【BUG ①】TCM 体质测评提交（用普通用户）")
print("=" * 60)
# 先注册/登录用户
reg_data = json.dumps({"phone": "13900099991", "password": "user12345", "nickname": "测试E2E"}).encode()
fetch("/api/auth/register", method="POST", headers={"Content-Type": "application/json"}, data=reg_data)
login_data = json.dumps({"phone": "13900099991", "password": "user12345"}).encode()
status, _, body = fetch("/api/auth/login", method="POST",
                         headers={"Content-Type": "application/json"}, data=login_data)
if status == 200:
    user_token = json.loads(body).get("access_token")
    # 提交体质测评
    payload = json.dumps({
        "answers": [
            {"question_id": 1, "answer_value": "经常"},
            {"question_id": 2, "answer_value": "偶尔"},
        ]
    }).encode()
    s, h, b = fetch("/api/tcm/constitution-test", method="POST",
                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {user_token}"},
                     data=payload)
    print(f"  HTTP {s}")
    print(f"  body[:500] = {b[:500].decode('utf-8', 'replace')}")
    # 测试空 answers 应当 422
    payload2 = json.dumps({"answers": []}).encode()
    s2, _, b2 = fetch("/api/tcm/constitution-test", method="POST",
                      headers={"Content-Type": "application/json", "Authorization": f"Bearer {user_token}"},
                      data=payload2)
    print(f"  空 answers HTTP {s2}（期望 422）→ {b2[:200].decode('utf-8', 'replace')}")

print("\n=== 全部验证完成 ===")
