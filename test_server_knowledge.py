import httpx
import sys

BASE = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
passed = 0
failed = 0
errors = []

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  PASS: {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  FAIL: {name} -> {e}")

client = httpx.Client(timeout=30, verify=False)

admin_token = None
user_token = None

def login_admin():
    global admin_token
    r = client.post(f"{BASE}/admin/login", json={"phone": "13800000000", "password": "admin123"})
    if r.status_code == 200:
        data = r.json()
        admin_token = data.get("access_token") or data.get("token")
    if not admin_token:
        raise Exception(f"Cannot login as admin: status={r.status_code}, body={r.text[:300]}")

def headers(token=None):
    t = token or admin_token
    return {"Authorization": f"Bearer {t}"} if t else {}

print("=== Server Knowledge Base API Tests ===\n")

# Login
try:
    login_admin()
    print(f"  Admin login OK (token={admin_token[:20]}...)")
except Exception as e:
    print(f"  Admin login FAILED: {e}")
    sys.exit(1)

kb_id = None
entry_id = None

# 1. Knowledge Base CRUD
print("\n--- Knowledge Base CRUD ---")

def test_create_kb():
    global kb_id
    r = client.post(f"{BASE}/admin/knowledge-bases", json={
        "name": "测试知识库",
        "description": "自动化测试用"
    }, headers=headers())
    assert r.status_code in (200, 201), f"status={r.status_code}, body={r.text[:200]}"
    data = r.json()
    kb_id = data.get("id")
    assert kb_id, f"No id returned: {data}"
test("创建知识库", test_create_kb)

def test_list_kb():
    r = client.get(f"{BASE}/admin/knowledge-bases", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
    data = r.json()
    assert "items" in data or isinstance(data, list), f"unexpected: {str(data)[:200]}"
test("获取知识库列表", test_list_kb)

def test_update_kb():
    r = client.put(f"{BASE}/admin/knowledge-bases/{kb_id}", json={
        "name": "测试知识库-已更新",
        "description": "更新后的描述"
    }, headers=headers())
    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
test("更新知识库", test_update_kb)

def test_no_auth_kb():
    r = client.get(f"{BASE}/admin/knowledge-bases")
    assert r.status_code == 401, f"expected 401, got {r.status_code}"
test("未认证访问知识库", test_no_auth_kb)

# 2. Knowledge Entry CRUD
print("\n--- Knowledge Entry CRUD ---")

def test_create_qa_entry():
    global entry_id
    r = client.post(f"{BASE}/admin/knowledge-bases/{kb_id}/entries", json={
        "type": "qa",
        "question": "什么是维生素C？",
        "content_json": {"text": "维生素C是一种水溶性维生素，对人体健康至关重要。"},
        "keywords": ["维生素C", "营养", "健康"],
        "display_mode": "direct"
    }, headers=headers())
    assert r.status_code in (200, 201), f"status={r.status_code}, body={r.text[:300]}"
    data = r.json()
    entry_id = data.get("id")
    assert entry_id, f"No id: {data}"
test("创建QA条目", test_create_qa_entry)

def test_create_doc_entry():
    r = client.post(f"{BASE}/admin/knowledge-bases/{kb_id}/entries", json={
        "type": "doc",
        "title": "健康饮食指南",
        "content_json": {"text": "均衡饮食是保持健康的关键。"},
        "keywords": ["饮食", "健康"],
        "display_mode": "ai_rewrite"
    }, headers=headers())
    assert r.status_code in (200, 201), f"status={r.status_code}, body={r.text[:300]}"
test("创建文档条目", test_create_doc_entry)

def test_list_entries():
    r = client.get(f"{BASE}/admin/knowledge-bases/{kb_id}/entries", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    assert len(items) >= 2, f"expected >= 2 entries, got {len(items)}"
test("获取条目列表", test_list_entries)

def test_update_entry():
    r = client.put(f"{BASE}/admin/knowledge-bases/{kb_id}/entries/{entry_id}", json={
        "question": "维生素C有什么作用？",
        "keywords": ["维生素C", "作用", "功效"]
    }, headers=headers())
    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
test("更新条目", test_update_entry)

def test_search_entries():
    r = client.get(f"{BASE}/admin/knowledge-bases/{kb_id}/entries?keyword=维生素", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
test("搜索条目", test_search_entries)

# 3. Search & Fallback Config
print("\n--- Search & Fallback Config ---")

def test_get_search_config():
    r = client.get(f"{BASE}/admin/knowledge-bases/search-config", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
test("获取全局检索策略", test_get_search_config)

def test_update_search_config():
    r = client.put(f"{BASE}/admin/knowledge-bases/search-config", json={
        "scope": "global",
        "config_json": {
            "exact_match_enabled": True,
            "semantic_match_enabled": True,
            "keyword_match_enabled": True,
            "similarity_threshold": "standard",
            "max_results": 3
        }
    }, headers=headers())
    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
test("更新全局检索策略", test_update_search_config)

def test_get_fallback():
    r = client.get(f"{BASE}/admin/knowledge-bases/fallback-config", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
test("获取兜底策略", test_get_fallback)

def test_update_fallback():
    r = client.put(f"{BASE}/admin/knowledge-bases/fallback-config", json={
        "scene": "health_qa",
        "strategy": "ai_fallback",
        "custom_text": "",
        "recommend_count": 3
    }, headers=headers())
    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
test("更新兜底策略", test_update_fallback)

def test_get_scene_bindings():
    r = client.get(f"{BASE}/admin/knowledge-bases/scene-bindings", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
test("获取场景绑定", test_get_scene_bindings)

def test_update_scene_bindings():
    r = client.put(f"{BASE}/admin/knowledge-bases/scene-bindings", json=[
        {"scene": "health_qa", "kb_id": kb_id, "is_primary": True}
    ], headers=headers())
    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
test("更新场景绑定", test_update_scene_bindings)

# 4. Statistics
print("\n--- Statistics ---")

def test_stats_overview():
    r = client.get(f"{BASE}/admin/knowledge-bases/stats/overview", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
test("统计概览", test_stats_overview)

def test_stats_top_hits():
    r = client.get(f"{BASE}/admin/knowledge-bases/stats/top-hits", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
test("命中排行", test_stats_top_hits)

def test_stats_missed():
    r = client.get(f"{BASE}/admin/knowledge-bases/stats/missed-questions", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
test("未命中问题", test_stats_missed)

def test_stats_trend():
    r = client.get(f"{BASE}/admin/knowledge-bases/stats/trend", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
test("命中率趋势", test_stats_trend)

def test_stats_distribution():
    r = client.get(f"{BASE}/admin/knowledge-bases/stats/distribution", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
test("命中分布", test_stats_distribution)

# 5. COS Config
print("\n--- COS Config ---")

def test_cos_get_config():
    r = client.get(f"{BASE}/admin/cos/config", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
test("获取COS配置", test_cos_get_config)

def test_cos_update_config():
    r = client.put(f"{BASE}/admin/cos/config", json={
        "bucket": "test-bucket",
        "region": "ap-guangzhou",
        "image_prefix": "images/",
        "video_prefix": "videos/",
        "file_prefix": "files/"
    }, headers=headers())
    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
test("更新COS配置", test_cos_update_config)

def test_cos_files():
    r = client.get(f"{BASE}/admin/cos/files", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
test("获取COS文件列表", test_cos_files)

def test_cos_usage():
    r = client.get(f"{BASE}/admin/cos/usage", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
test("获取COS用量", test_cos_usage)

# 6. Cleanup
print("\n--- Cleanup ---")

def test_delete_entry():
    r = client.delete(f"{BASE}/admin/knowledge-bases/{kb_id}/entries/{entry_id}", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}"
test("删除条目", test_delete_entry)

def test_delete_kb():
    r = client.delete(f"{BASE}/admin/knowledge-bases/{kb_id}?confirm=true", headers=headers())
    assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
test("删除知识库", test_delete_kb)

# Summary
print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed, {passed+failed} total")
if errors:
    print("\nFailed tests:")
    for name, err in errors:
        print(f"  - {name}: {err}")
print(f"{'='*50}")
