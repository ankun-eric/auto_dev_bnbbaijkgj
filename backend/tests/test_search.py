"""
统一搜索功能 — 非 UI 自动化测试
覆盖公共接口、用户认证接口、管理员接口及搜索业务逻辑。
"""

import pytest
from httpx import AsyncClient


# ════════════════════════════════════════════
#  1. 公共接口测试（无需认证）
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc001_hot_keywords(client: AsyncClient):
    """TC-001: GET /api/search/hot 获取热门搜索词，返回200"""
    resp = await client.get("/api/search/hot")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_tc002_suggest(client: AsyncClient):
    """TC-002: GET /api/search/suggest?q=测试 联想词建议，返回200"""
    resp = await client.get("/api/search/suggest", params={"q": "测试"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_tc003_drug_keywords(client: AsyncClient):
    """TC-003: GET /api/search/drug-keywords 获取拍照识药触发词，返回200"""
    resp = await client.get("/api/search/drug-keywords")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_tc004_unified_search_all(client: AsyncClient):
    """TC-004: GET /api/search?q=健康&type=all 统一搜索，返回200"""
    resp = await client.get("/api/search", params={"q": "健康", "type": "all"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "type_counts" in data
    assert isinstance(data["type_counts"], dict)
    for key in ("article", "video", "service", "points_mall"):
        assert key in data["type_counts"]


@pytest.mark.asyncio
async def test_tc005_unified_search_by_type(client: AsyncClient):
    """TC-005: GET /api/search?q=健康&type=article 按类别搜索，返回200"""
    resp = await client.get("/api/search", params={"q": "健康", "type": "article"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    for item in data["items"]:
        assert item["type"] == "article"


@pytest.mark.asyncio
async def test_tc006_asr_token_disabled(client: AsyncClient):
    """TC-006: POST /api/search/asr/token 未配置时返回 400"""
    resp = await client.post("/api/search/asr/token")
    assert resp.status_code == 400
    assert "未启用" in resp.json().get("detail", "")


# ════════════════════════════════════════════
#  2. 需要用户认证的接口
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc007_history_no_auth(client: AsyncClient):
    """TC-007: GET /api/search/history 未登录返回401"""
    resp = await client.get("/api/search/history")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tc008_history_with_auth(client: AsyncClient, auth_headers: dict):
    """TC-008: GET /api/search/history 登录后返回200和历史列表"""
    resp = await client.get("/api/search/history", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_tc009_clear_history_no_auth(client: AsyncClient):
    """TC-009: DELETE /api/search/history 未登录返回401"""
    resp = await client.delete("/api/search/history")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tc010_clear_history_with_auth(client: AsyncClient, auth_headers: dict):
    """TC-010: DELETE /api/search/history 登录后清空历史返回成功"""
    resp = await client.delete("/api/search/history", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json().get("message") == "已清空搜索历史"


# ════════════════════════════════════════════
#  3. 管理员接口（需要 admin 认证）
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc011_admin_recommend_words_list(client: AsyncClient, admin_headers: dict):
    """TC-011: GET /api/admin/search/recommend-words 管理员获取推荐词列表"""
    resp = await client.get("/api/admin/search/recommend-words", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_tc012_admin_create_recommend_word(client: AsyncClient, admin_headers: dict):
    """TC-012: POST /api/admin/search/recommend-words 新增推荐词"""
    payload = {"keyword": "自动化测试推荐词", "sort_order": 1, "is_active": True}
    resp = await client.post("/api/admin/search/recommend-words", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["keyword"] == "自动化测试推荐词"
    assert "id" in data


@pytest.mark.asyncio
async def test_tc013_admin_update_recommend_word(client: AsyncClient, admin_headers: dict):
    """TC-013: PUT /api/admin/search/recommend-words/{id} 编辑推荐词"""
    create_resp = await client.post(
        "/api/admin/search/recommend-words",
        json={"keyword": "待编辑推荐词", "sort_order": 0},
        headers=admin_headers,
    )
    word_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/admin/search/recommend-words/{word_id}",
        json={"keyword": "已编辑推荐词", "sort_order": 5},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["keyword"] == "已编辑推荐词"
    assert update_resp.json()["sort_order"] == 5


@pytest.mark.asyncio
async def test_tc014_admin_delete_recommend_word(client: AsyncClient, admin_headers: dict):
    """TC-014: DELETE /api/admin/search/recommend-words/{id} 删除推荐词"""
    create_resp = await client.post(
        "/api/admin/search/recommend-words",
        json={"keyword": "待删除推荐词"},
        headers=admin_headers,
    )
    word_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/admin/search/recommend-words/{word_id}", headers=admin_headers)
    assert del_resp.status_code == 200
    assert del_resp.json().get("message") == "删除成功"


@pytest.mark.asyncio
async def test_tc015_admin_search_statistics(client: AsyncClient, admin_headers: dict):
    """TC-015: GET /api/admin/search/statistics 搜索统计"""
    resp = await client.get("/api/admin/search/statistics", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "top_keywords" in data
    assert "trend" in data
    assert "no_result_keywords" in data
    assert "type_distribution" in data


@pytest.mark.asyncio
async def test_tc016_admin_block_words_list(client: AsyncClient, admin_headers: dict):
    """TC-016: GET /api/admin/search/block-words 屏蔽词列表"""
    resp = await client.get("/api/admin/search/block-words", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_tc017_admin_create_block_word(client: AsyncClient, admin_headers: dict):
    """TC-017: POST /api/admin/search/block-words 新增屏蔽词"""
    payload = {"keyword": "测试屏蔽词A", "block_mode": "full", "is_active": True}
    resp = await client.post("/api/admin/search/block-words", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["keyword"] == "测试屏蔽词A"
    assert "id" in data


@pytest.mark.asyncio
async def test_tc018_admin_update_block_word(client: AsyncClient, admin_headers: dict):
    """TC-018: PUT /api/admin/search/block-words/{id} 编辑屏蔽词"""
    create_resp = await client.post(
        "/api/admin/search/block-words",
        json={"keyword": "待编辑屏蔽词"},
        headers=admin_headers,
    )
    word_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/admin/search/block-words/{word_id}",
        json={"block_mode": "tip", "tip_content": "该关键词已被屏蔽"},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["block_mode"] == "tip"
    assert update_resp.json()["tip_content"] == "该关键词已被屏蔽"


@pytest.mark.asyncio
async def test_tc019_admin_delete_block_word(client: AsyncClient, admin_headers: dict):
    """TC-019: DELETE /api/admin/search/block-words/{id} 删除屏蔽词"""
    create_resp = await client.post(
        "/api/admin/search/block-words",
        json={"keyword": "待删除屏蔽词"},
        headers=admin_headers,
    )
    word_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/admin/search/block-words/{word_id}", headers=admin_headers)
    assert del_resp.status_code == 200
    assert del_resp.json().get("message") == "删除成功"


@pytest.mark.asyncio
async def test_tc020_admin_batch_import_block_words(client: AsyncClient, admin_headers: dict):
    """TC-020: POST /api/admin/search/block-words/batch 批量导入屏蔽词"""
    payload = {
        "keywords": ["批量词A", "批量词B", "批量词C"],
        "block_mode": "full",
    }
    resp = await client.post("/api/admin/search/block-words/batch", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["added"] == 3
    assert data["skipped"] == 0
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_tc021_admin_asr_config_get(client: AsyncClient, admin_headers: dict):
    """TC-021: GET /api/admin/search/asr-config 获取ASR配置（无配置时404）"""
    resp = await client.get("/api/admin/search/asr-config", headers=admin_headers)
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_tc022_admin_asr_config_update(client: AsyncClient, admin_headers: dict):
    """TC-022: PUT /api/admin/search/asr-config 更新ASR配置"""
    payload = {
        "provider": "tencent",
        "app_id": "test_app_id",
        "secret_id": "test_secret_id",
        "secret_key_raw": "test_secret_key_value",
        "is_enabled": True,
        "supported_dialects": "普通话,粤语,英语",
    }
    resp = await client.put("/api/admin/search/asr-config", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "tencent"
    assert data["app_id"] == "test_app_id"
    assert data["is_enabled"] is True
    # secret_key should be masked
    assert "****" in data.get("secret_key_encrypted", "")


@pytest.mark.asyncio
async def test_tc023_admin_asr_config_test(client: AsyncClient, admin_headers: dict):
    """TC-023: POST /api/admin/search/asr-config/test 测试ASR配置"""
    # First ensure config exists
    await client.put(
        "/api/admin/search/asr-config",
        json={
            "provider": "tencent",
            "app_id": "test_app",
            "secret_id": "test_sid",
            "secret_key_raw": "test_skey_value",
            "is_enabled": True,
        },
        headers=admin_headers,
    )

    resp = await client.post("/api/admin/search/asr-config/test", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_tc024_admin_endpoints_require_admin(client: AsyncClient, auth_headers: dict):
    """TC-024: 非管理员访问管理接口返回401/403"""
    endpoints = [
        ("GET", "/api/admin/search/recommend-words"),
        ("POST", "/api/admin/search/recommend-words"),
        ("GET", "/api/admin/search/block-words"),
        ("POST", "/api/admin/search/block-words"),
        ("GET", "/api/admin/search/statistics"),
        ("GET", "/api/admin/search/asr-config"),
        ("PUT", "/api/admin/search/asr-config"),
        ("POST", "/api/admin/search/asr-config/test"),
    ]
    for method, path in endpoints:
        if method == "GET":
            resp = await client.get(path, headers=auth_headers)
        elif method == "POST":
            resp = await client.post(path, json={}, headers=auth_headers)
        elif method == "PUT":
            resp = await client.put(path, json={}, headers=auth_headers)
        else:
            resp = await client.delete(path, headers=auth_headers)
        assert resp.status_code in (401, 403), (
            f"{method} {path} expected 401/403 for normal user, got {resp.status_code}"
        )

    # Also verify completely unauthenticated access is rejected
    resp_no_auth = await client.get("/api/admin/search/recommend-words")
    assert resp_no_auth.status_code == 401


# ════════════════════════════════════════════
#  4. 搜索业务逻辑测试
# ════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tc025_search_records_history(client: AsyncClient, auth_headers: dict):
    """TC-025: 登录用户搜索后 GET 历史应包含搜索词"""
    unique_kw = "自动化测试历史词XYZ"
    search_resp = await client.get("/api/search", params={"q": unique_kw, "type": "all"}, headers=auth_headers)
    assert search_resp.status_code == 200

    history_resp = await client.get("/api/search/history", headers=auth_headers)
    assert history_resp.status_code == 200
    keywords = [h["keyword"] for h in history_resp.json()]
    assert unique_kw in keywords


@pytest.mark.asyncio
async def test_tc026_block_word_hides_results(client: AsyncClient, admin_headers: dict):
    """TC-026: 添加屏蔽词后搜索该词应返回空结果"""
    block_kw = "严禁搜索测试词"

    # Admin adds block word
    create_resp = await client.post(
        "/api/admin/search/block-words",
        json={"keyword": block_kw, "block_mode": "full", "is_active": True},
        headers=admin_headers,
    )
    assert create_resp.status_code == 200

    # Search the blocked keyword
    search_resp = await client.get("/api/search", params={"q": block_kw, "type": "all"})
    assert search_resp.status_code == 200
    data = search_resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_tc026b_block_word_tip_mode(client: AsyncClient, admin_headers: dict):
    """TC-026b: 屏蔽词 tip 模式返回提示文案"""
    block_kw = "提示屏蔽词测试"
    tip_text = "该关键词已被管理员屏蔽"

    await client.post(
        "/api/admin/search/block-words",
        json={"keyword": block_kw, "block_mode": "tip", "tip_content": tip_text, "is_active": True},
        headers=admin_headers,
    )

    search_resp = await client.get("/api/search", params={"q": block_kw, "type": "all"})
    assert search_resp.status_code == 200
    data = search_resp.json()
    assert data["total"] == 0
    assert data["block_tip"] == tip_text


@pytest.mark.asyncio
async def test_tc027_search_log(client: AsyncClient):
    """TC-027: POST /api/search/log 记录搜索点击"""
    payload = {
        "keyword": "测试点击日志",
        "clicked_type": "article",
        "clicked_item_id": 1,
    }
    resp = await client.post("/api/search/log", json=payload)
    assert resp.status_code == 200
    assert resp.json().get("message") == "记录成功"
