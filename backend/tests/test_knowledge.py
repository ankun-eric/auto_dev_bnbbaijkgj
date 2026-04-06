"""Tests for knowledge-base management & COS storage APIs."""

import pytest
from httpx import AsyncClient

from app.core.security import get_password_hash
from app.models.models import (
    CosConfig,
    CosFile,
    KnowledgeBase,
    KnowledgeEntry,
    KnowledgeFallbackConfig,
    KnowledgeHitLog,
    KnowledgeMissedQuestion,
    KnowledgeSceneBinding,
    KnowledgeSearchConfig,
    User,
    UserRole,
)

from .conftest import test_session


# ─── helpers ───


async def _create_admin(db_session, phone="13800200001") -> User:
    user = User(
        phone=phone,
        password_hash=get_password_hash("admin123"),
        nickname="知识库管理员",
        role=UserRole.admin,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _admin_headers(client: AsyncClient, phone="13800200001", password="admin123"):
    resp = await client.post("/api/admin/login", json={"phone": phone, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


async def _create_user(client: AsyncClient, phone="13900200001", password="user123", nickname="普通用户"):
    resp = await client.post("/api/auth/register", json={
        "phone": phone, "password": password, "nickname": nickname,
    })
    assert resp.status_code == 200
    return resp.json()


async def _user_headers(client: AsyncClient, phone="13900200001", password="user123"):
    resp = await client.post("/api/auth/login", json={"phone": phone, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_kb(client: AsyncClient, headers: dict, name="测试知识库", description="测试描述") -> dict:
    resp = await client.post("/api/admin/knowledge-bases", json={
        "name": name, "description": description,
    }, headers=headers)
    assert resp.status_code == 200
    return resp.json()


async def _create_entry(
    client: AsyncClient, headers: dict, kb_id: int,
    entry_type="qa", question="什么是高血压？", title="高血压定义",
) -> dict:
    resp = await client.post(f"/api/admin/knowledge-bases/{kb_id}/entries", json={
        "type": entry_type,
        "question": question,
        "title": title,
        "content_json": {"answer": "高血压是血压持续偏高的一种慢性病。"},
        "keywords": ["高血压", "血压"],
    }, headers=headers)
    assert resp.status_code == 200
    return resp.json()


# ═══════════════════════════════════════════════════════════════
#  1. 知识库 CRUD 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_kb_crud_01_unauthorized(client: AsyncClient):
    """未认证访问返回401"""
    resp = await client.get("/api/admin/knowledge-bases")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_kb_crud_02_forbidden(client: AsyncClient):
    """非管理员访问返回403"""
    await _create_user(client, phone="13900200002")
    headers = await _user_headers(client, phone="13900200002")
    resp = await client.get("/api/admin/knowledge-bases", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_kb_crud_03_create(client: AsyncClient, db_session):
    """管理员创建知识库"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.post("/api/admin/knowledge-bases", json={
        "name": "健康百科", "description": "健康知识库", "is_global": True,
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "健康百科"
    assert data["description"] == "健康知识库"
    assert data["is_global"] is True
    assert data["status"] == "active"
    assert data["id"] > 0


@pytest.mark.asyncio
async def test_kb_crud_04_list(client: AsyncClient, db_session):
    """管理员获取知识库列表"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    await _create_kb(client, headers, name="知识库A")
    await _create_kb(client, headers, name="知识库B")

    resp = await client.get("/api/admin/knowledge-bases", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 2
    names = [item["name"] for item in data["items"]]
    assert "知识库A" in names
    assert "知识库B" in names


@pytest.mark.asyncio
async def test_kb_crud_05_update(client: AsyncClient, db_session):
    """管理员更新知识库"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers, name="旧名称")

    resp = await client.put(f"/api/admin/knowledge-bases/{kb['id']}", json={
        "name": "新名称", "description": "更新描述",
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "新名称"
    assert data["description"] == "更新描述"


@pytest.mark.asyncio
async def test_kb_crud_06_toggle_status(client: AsyncClient, db_session):
    """管理员启用/禁用知识库"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)

    resp = await client.put(f"/api/admin/knowledge-bases/{kb['id']}", json={
        "status": "disabled",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"

    resp2 = await client.put(f"/api/admin/knowledge-bases/{kb['id']}", json={
        "status": "active",
    }, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "active"


@pytest.mark.asyncio
async def test_kb_crud_07_delete(client: AsyncClient, db_session):
    """管理员删除知识库（需二次确认）"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)

    resp1 = await client.delete(
        f"/api/admin/knowledge-bases/{kb['id']}", headers=headers,
    )
    assert resp1.status_code == 200
    assert resp1.json()["require_confirm"] is True

    resp2 = await client.delete(
        f"/api/admin/knowledge-bases/{kb['id']}", params={"confirm": True}, headers=headers,
    )
    assert resp2.status_code == 200
    assert "删除成功" in resp2.json()["message"]

    resp3 = await client.delete(
        f"/api/admin/knowledge-bases/{kb['id']}", params={"confirm": True}, headers=headers,
    )
    assert resp3.status_code == 404


@pytest.mark.asyncio
async def test_kb_crud_08_create_missing_name(client: AsyncClient, db_session):
    """创建知识库缺少必填字段name返回422"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.post("/api/admin/knowledge-bases", json={
        "description": "没有name",
    }, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_kb_crud_09_list_keyword_filter(client: AsyncClient, db_session):
    """按关键词筛选知识库列表"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    await _create_kb(client, headers, name="中医养生")
    await _create_kb(client, headers, name="营养食谱")

    resp = await client.get("/api/admin/knowledge-bases", params={"keyword": "中医"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert all("中医" in item["name"] for item in data["items"])


# ═══════════════════════════════════════════════════════════════
#  2. 知识条目 CRUD 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_entry_crud_01_create_qa(client: AsyncClient, db_session):
    """创建QA类型条目"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)

    entry = await _create_entry(client, headers, kb["id"])
    assert entry["type"] == "qa"
    assert entry["question"] == "什么是高血压？"
    assert entry["kb_id"] == kb["id"]
    assert entry["status"] == "active"


@pytest.mark.asyncio
async def test_entry_crud_02_create_doc(client: AsyncClient, db_session):
    """创建文档类型条目"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)

    resp = await client.post(f"/api/admin/knowledge-bases/{kb['id']}/entries", json={
        "type": "doc",
        "title": "用药指南",
        "content_json": {"body": "用药须知..."},
        "display_mode": "ai_rewrite",
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "doc"
    assert data["title"] == "用药指南"
    assert data["display_mode"] == "ai_rewrite"


@pytest.mark.asyncio
async def test_entry_crud_03_list_pagination(client: AsyncClient, db_session):
    """获取条目列表（分页）"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)

    for i in range(5):
        await _create_entry(client, headers, kb["id"], question=f"问题{i}", title=f"标题{i}")

    resp = await client.get(
        f"/api/admin/knowledge-bases/{kb['id']}/entries",
        params={"page": 1, "page_size": 2},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_entry_crud_04_search_keyword(client: AsyncClient, db_session):
    """搜索条目（关键词过滤）"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)

    await _create_entry(client, headers, kb["id"], question="感冒了怎么办？", title="感冒指南")
    await _create_entry(client, headers, kb["id"], question="糖尿病注意事项", title="糖尿病")

    resp = await client.get(
        f"/api/admin/knowledge-bases/{kb['id']}/entries",
        params={"keyword": "感冒"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert "感冒" in (item.get("question") or "") or "感冒" in (item.get("title") or "")


@pytest.mark.asyncio
async def test_entry_crud_05_update(client: AsyncClient, db_session):
    """更新条目"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)
    entry = await _create_entry(client, headers, kb["id"])

    resp = await client.put(
        f"/api/admin/knowledge-bases/{kb['id']}/entries/{entry['id']}",
        json={"question": "更新后的问题", "status": "disabled"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["question"] == "更新后的问题"
    assert data["status"] == "disabled"


@pytest.mark.asyncio
async def test_entry_crud_06_delete(client: AsyncClient, db_session):
    """删除条目"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)
    entry = await _create_entry(client, headers, kb["id"])

    resp = await client.delete(
        f"/api/admin/knowledge-bases/{kb['id']}/entries/{entry['id']}",
        headers=headers,
    )
    assert resp.status_code == 200
    assert "删除成功" in resp.json()["message"]

    resp2 = await client.delete(
        f"/api/admin/knowledge-bases/{kb['id']}/entries/{entry['id']}",
        headers=headers,
    )
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_entry_crud_07_nonexistent_kb(client: AsyncClient, db_session):
    """条目关联不存在的知识库返回404"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.post("/api/admin/knowledge-bases/99999/entries", json={
        "type": "qa", "question": "不存在的知识库",
    }, headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_entry_crud_08_missing_type(client: AsyncClient, db_session):
    """条目缺少必填字段type返回422"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)

    resp = await client.post(f"/api/admin/knowledge-bases/{kb['id']}/entries", json={
        "question": "缺少type字段",
    }, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_entry_crud_09_filter_by_type(client: AsyncClient, db_session):
    """按类型筛选条目"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)

    await _create_entry(client, headers, kb["id"], entry_type="qa", question="QA问题")
    resp = await client.post(f"/api/admin/knowledge-bases/{kb['id']}/entries", json={
        "type": "doc", "title": "文档条目",
    }, headers=headers)
    assert resp.status_code == 200

    resp = await client.get(
        f"/api/admin/knowledge-bases/{kb['id']}/entries",
        params={"entry_type": "qa"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["type"] == "qa" for item in data["items"])


# ═══════════════════════════════════════════════════════════════
#  3. 检索策略和兜底策略测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_search_config_01_get_global(client: AsyncClient, db_session):
    """获取全局检索策略配置（默认值）"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.get("/api/admin/knowledge-bases/search-config", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == "global"
    assert "config_json" in data


@pytest.mark.asyncio
async def test_search_config_02_update_global(client: AsyncClient, db_session):
    """更新全局检索策略配置"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    new_config = {"match_threshold": 0.8, "max_results": 5, "enable_semantic": True}
    resp = await client.put("/api/admin/knowledge-bases/search-config", json={
        "scope": "global", "config_json": new_config,
    }, headers=headers)
    assert resp.status_code == 200
    assert "更新成功" in resp.json()["message"]

    resp2 = await client.get("/api/admin/knowledge-bases/search-config", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["config_json"]["match_threshold"] == 0.8


@pytest.mark.asyncio
async def test_search_config_03_get_kb_level(client: AsyncClient, db_session):
    """获取知识库级检索策略（默认无配置）"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)

    resp = await client.get(
        f"/api/admin/knowledge-bases/{kb['id']}/search-config", headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == f"kb_{kb['id']}"
    assert data["config_json"] is None


@pytest.mark.asyncio
async def test_search_config_04_update_kb_level(client: AsyncClient, db_session):
    """更新知识库级检索策略"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)

    resp = await client.put(
        f"/api/admin/knowledge-bases/{kb['id']}/search-config",
        json={"scope": f"kb_{kb['id']}", "config_json": {"max_results": 10}},
        headers=headers,
    )
    assert resp.status_code == 200
    assert "更新成功" in resp.json()["message"]


@pytest.mark.asyncio
async def test_fallback_config_01_get_default(client: AsyncClient, db_session):
    """获取兜底策略配置（默认值）"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.get("/api/admin/knowledge-bases/fallback-config", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["scene"] == "default"
    assert data["strategy"] == "ai_fallback"
    assert data["recommend_count"] == 3


@pytest.mark.asyncio
async def test_fallback_config_02_update(client: AsyncClient, db_session):
    """更新兜底策略配置"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.put("/api/admin/knowledge-bases/fallback-config", json={
        "scene": "default",
        "strategy": "fixed_text",
        "custom_text": "暂时无法回答，请稍后再试",
        "recommend_count": 5,
    }, headers=headers)
    assert resp.status_code == 200
    assert "更新成功" in resp.json()["message"]

    resp2 = await client.get(
        "/api/admin/knowledge-bases/fallback-config",
        params={"scene": "default"},
        headers=headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["strategy"] == "fixed_text"
    assert resp2.json()["custom_text"] == "暂时无法回答，请稍后再试"


@pytest.mark.asyncio
async def test_scene_binding_01_get_empty(client: AsyncClient, db_session):
    """获取场景绑定（初始为空）"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.get("/api/admin/knowledge-bases/scene-bindings", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_scene_binding_02_update_and_get(client: AsyncClient, db_session):
    """更新并获取场景绑定"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)

    resp = await client.put("/api/admin/knowledge-bases/scene-bindings", json=[
        {"scene": "health_qa", "kb_id": kb["id"], "is_primary": True},
    ], headers=headers)
    assert resp.status_code == 200
    assert "更新成功" in resp.json()["message"]

    resp2 = await client.get(
        "/api/admin/knowledge-bases/scene-bindings",
        params={"scene": "health_qa"},
        headers=headers,
    )
    assert resp2.status_code == 200
    items = resp2.json()["items"]
    assert len(items) >= 1
    assert items[0]["kb_id"] == kb["id"]
    assert items[0]["is_primary"] is True


# ═══════════════════════════════════════════════════════════════
#  4. 统计 API 测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_stats_01_overview_empty(client: AsyncClient, db_session):
    """获取统计概览（无数据时返回零值）"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.get("/api/admin/knowledge-bases/stats/overview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_knowledge_bases"] == 0
    assert data["total_entries"] == 0
    assert data["total_hits"] == 0
    assert data["hit_rate"] == 0.0


@pytest.mark.asyncio
async def test_stats_02_overview_with_data(client: AsyncClient, db_session):
    """创建数据后统计概览有值"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)
    await _create_entry(client, headers, kb["id"])

    resp = await client.get("/api/admin/knowledge-bases/stats/overview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_knowledge_bases"] >= 1
    assert data["total_entries"] >= 1


@pytest.mark.asyncio
async def test_stats_03_top_hits_empty(client: AsyncClient, db_session):
    """获取命中排行（无命中数据）"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.get("/api/admin/knowledge-bases/stats/top-hits", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_stats_04_missed_questions(client: AsyncClient, db_session):
    """获取未命中问题列表"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    async with test_session() as s:
        s.add(KnowledgeMissedQuestion(question="未收录的问题", scene="health_qa", count=3))
        await s.commit()

    resp = await client.get("/api/admin/knowledge-bases/stats/missed-questions", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(q["question"] == "未收录的问题" for q in data["items"])


@pytest.mark.asyncio
async def test_stats_05_trend(client: AsyncClient, db_session):
    """获取命中率趋势"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.get(
        "/api/admin/knowledge-bases/stats/trend", params={"days": 7}, headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) == 7
    for point in data["items"]:
        assert "date" in point
        assert "hits" in point
        assert "misses" in point


@pytest.mark.asyncio
async def test_stats_06_distribution(client: AsyncClient, db_session):
    """获取命中分布"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.get("/api/admin/knowledge-bases/stats/distribution", headers=headers)
    assert resp.status_code == 200
    assert "items" in resp.json()


# ═══════════════════════════════════════════════════════════════
#  5. COS 配置测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_cos_01_get_config_empty(client: AsyncClient, db_session):
    """获取COS配置（无配置时返回默认值）"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.get("/api/admin/cos/config", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False
    assert data["image_prefix"] == "images/"


@pytest.mark.asyncio
async def test_cos_02_update_config(client: AsyncClient, db_session):
    """更新COS配置"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.put("/api/admin/cos/config", json={
        "secret_id": "AKIDtestxxxx",
        "secret_key": "test_secret_key",
        "bucket": "test-bucket-1250000000",
        "region": "ap-guangzhou",
        "is_active": True,
    }, headers=headers)
    assert resp.status_code == 200
    assert "更新成功" in resp.json()["message"]

    resp2 = await client.get("/api/admin/cos/config", headers=headers)
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["secret_id"] == "AKIDtestxxxx"
    assert data["bucket"] == "test-bucket-1250000000"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_cos_03_file_list_empty(client: AsyncClient, db_session):
    """获取文件列表（无文件）"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.get("/api/admin/cos/files", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_cos_04_usage_empty(client: AsyncClient, db_session):
    """获取用量统计（无文件）"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.get("/api/admin/cos/usage", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_files"] == 0
    assert data["total_size"] == 0
    assert data["total_size_mb"] == 0.0


@pytest.mark.asyncio
async def test_cos_05_usage_with_files(client: AsyncClient, db_session):
    """有文件记录时用量统计正确"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    async with test_session() as s:
        s.add(CosFile(
            file_key="images/test1.jpg",
            file_url="https://bucket.cos.ap-guangzhou.myqcloud.com/images/test1.jpg",
            file_type="image/jpeg",
            file_size=1024 * 100,
            original_name="test1.jpg",
            module="knowledge",
        ))
        s.add(CosFile(
            file_key="files/test2.pdf",
            file_url="https://bucket.cos.ap-guangzhou.myqcloud.com/files/test2.pdf",
            file_type="application/pdf",
            file_size=1024 * 500,
            original_name="test2.pdf",
            module="knowledge",
        ))
        await s.commit()

    resp = await client.get("/api/admin/cos/usage", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_files"] == 2
    assert data["total_size"] == 1024 * 600


@pytest.mark.asyncio
async def test_cos_06_file_list_with_module_filter(client: AsyncClient, db_session):
    """按模块筛选文件列表"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    async with test_session() as s:
        s.add(CosFile(
            file_key="images/mod_a.jpg", file_url="/uploads/mod_a.jpg",
            file_type="image/jpeg", file_size=100, module="avatar",
        ))
        s.add(CosFile(
            file_key="files/mod_b.pdf", file_url="/uploads/mod_b.pdf",
            file_type="application/pdf", file_size=200, module="knowledge",
        ))
        await s.commit()

    resp = await client.get("/api/admin/cos/files", params={"module": "knowledge"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["module"] == "knowledge"


@pytest.mark.asyncio
async def test_cos_07_unauthorized(client: AsyncClient):
    """未认证访问COS配置返回401"""
    resp = await client.get("/api/admin/cos/config")
    assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
#  6. 用户反馈测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_feedback_01_submit_like(client: AsyncClient, db_session):
    """提交点赞反馈"""
    admin = await _create_admin(db_session)
    headers = await _admin_headers(client)

    kb = await _create_kb(client, headers)
    entry = await _create_entry(client, headers, kb["id"])

    async with test_session() as s:
        hit_log = KnowledgeHitLog(
            entry_id=entry["id"],
            kb_id=kb["id"],
            match_type="exact",
            match_score=0.95,
            user_question="测试问题",
            search_time_ms=50,
        )
        s.add(hit_log)
        await s.commit()
        await s.refresh(hit_log)
        hit_log_id = hit_log.id

    resp = await client.post("/api/chat/feedback", json={
        "hit_log_id": hit_log_id,
        "feedback": "like",
    }, headers=headers)
    assert resp.status_code == 200
    assert "反馈已记录" in resp.json()["message"]


@pytest.mark.asyncio
async def test_feedback_02_unauthorized(client: AsyncClient):
    """未认证用户反馈返回401"""
    resp = await client.post("/api/chat/feedback", json={
        "hit_log_id": 1,
        "feedback": "like",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_feedback_03_user_submit_dislike(client: AsyncClient, db_session):
    """普通用户提交踩反馈"""
    admin = await _create_admin(db_session)
    admin_h = await _admin_headers(client)

    kb = await _create_kb(client, admin_h)
    entry = await _create_entry(client, admin_h, kb["id"])

    async with test_session() as s:
        hit_log = KnowledgeHitLog(
            entry_id=entry["id"],
            kb_id=kb["id"],
            match_type="semantic",
            match_score=0.7,
            user_question="测试问题2",
            search_time_ms=30,
        )
        s.add(hit_log)
        await s.commit()
        await s.refresh(hit_log)
        hit_log_id = hit_log.id

    await _create_user(client, phone="13900200099")
    user_h = await _user_headers(client, phone="13900200099")

    resp = await client.post("/api/chat/feedback", json={
        "hit_log_id": hit_log_id,
        "feedback": "dislike",
    }, headers=user_h)
    assert resp.status_code == 200
    assert "反馈已记录" in resp.json()["message"]


@pytest.mark.asyncio
async def test_feedback_04_nonexistent_hitlog(client: AsyncClient, db_session):
    """反馈不存在的命中记录返回404"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.post("/api/chat/feedback", json={
        "hit_log_id": 99999,
        "feedback": "like",
    }, headers=headers)
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════
#  7. 批量导入测试
# ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_import_01_preview_and_confirm(client: AsyncClient, db_session):
    """批量导入：预览 -> 确认"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)
    kb = await _create_kb(client, headers)

    resp = await client.post("/api/admin/knowledge-bases/import", json={
        "kb_id": kb["id"],
        "source_type": "excel",
        "entries": [
            {"type": "qa", "question": "导入问题1", "title": "标题1"},
            {"type": "qa", "question": "导入问题2", "title": "标题2"},
        ],
    }, headers=headers)
    assert resp.status_code == 200
    task = resp.json()
    assert task["status"] == "preview"
    assert task["kb_id"] == kb["id"]
    task_id = task["id"]

    resp2 = await client.get(f"/api/admin/knowledge-bases/import/{task_id}", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "preview"

    resp3 = await client.post(f"/api/admin/knowledge-bases/import/{task_id}/confirm", headers=headers)
    assert resp3.status_code == 200
    assert resp3.json()["created"] == 2

    resp4 = await client.get(
        f"/api/admin/knowledge-bases/{kb['id']}/entries", headers=headers,
    )
    assert resp4.status_code == 200
    assert resp4.json()["total"] >= 2


@pytest.mark.asyncio
async def test_import_02_nonexistent_kb(client: AsyncClient, db_session):
    """导入到不存在的知识库返回404"""
    await _create_admin(db_session)
    headers = await _admin_headers(client)

    resp = await client.post("/api/admin/knowledge-bases/import", json={
        "kb_id": 99999,
        "source_type": "csv",
        "entries": [{"type": "qa", "question": "q"}],
    }, headers=headers)
    assert resp.status_code == 404
