"""烟测：标签 CRUD 与商品打标 API"""
import requests

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
s = requests.Session()
s.verify = False
import urllib3
urllib3.disable_warnings()

def call(name, method, path, **kw):
    r = s.request(method, BASE + path, timeout=15, **kw)
    print(f"[{name}] {method} {path} -> {r.status_code}")
    try:
        j = r.json()
        if isinstance(j, dict) and 'data' in j:
            d = j['data']
            if isinstance(d, list):
                print(f"  data: list len={len(d)} first3={d[:3]}")
            else:
                print(f"  data: {str(d)[:300]}")
        else:
            print(f"  body: {str(j)[:300]}")
    except Exception:
        print(f"  text: {r.text[:200]}")
    return r

# 1) 标签列表
call("list_tags_constitution", "GET", "/api/admin/tags", params={"category": "constitution"})
call("list_tags_contraindication", "GET", "/api/admin/tags", params={"category": "contraindication"})
call("list_tags_all", "GET", "/api/admin/tags")

# 2) 商品列表（C端）
call("list_products", "GET", "/api/products", params={"page": 1, "page_size": 3})

# 3) 商品详情 + tags
r = s.get(BASE + "/api/products", params={"page": 1, "page_size": 1}, timeout=15)
try:
    j = r.json()
    items = j.get('data', {}).get('items') or j.get('items') or []
    if items:
        pid = items[0]['id']
        call("get_product_detail", "GET", f"/api/products/{pid}")
        call("related_products", "GET", f"/api/products/{pid}/related")
except Exception as e:
    print("无法获取商品 ID:", e)
