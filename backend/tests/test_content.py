import pytest
from httpx import AsyncClient

from app.models.models import Article, ContentStatus


async def _seed_articles():
    """Create test articles in the database."""
    from tests.conftest import test_session

    async with test_session() as db:
        a1 = Article(
            title="如何保持健康饮食",
            content="健康饮食的关键在于营养均衡...",
            category="nutrition",
            tags=["饮食", "健康"],
            status=ContentStatus.published,
            view_count=100,
            like_count=10,
        )
        a2 = Article(
            title="每日运动指南",
            content="适量运动对身体有很多好处...",
            category="fitness",
            tags=["运动", "健身"],
            status=ContentStatus.published,
            view_count=200,
            like_count=20,
        )
        a3 = Article(
            title="未发布的草稿",
            content="这是一篇草稿...",
            category="nutrition",
            status=ContentStatus.draft,
        )
        db.add_all([a1, a2, a3])
        await db.commit()
        return a1.id, a2.id, a3.id


@pytest.mark.asyncio
async def test_list_articles(client: AsyncClient):
    await _seed_articles()
    response = await client.get("/api/content/articles")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    for item in data["items"]:
        assert item["status"] == "published"


@pytest.mark.asyncio
async def test_list_articles_empty(client: AsyncClient):
    response = await client.get("/api/content/articles")
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_articles_by_category(client: AsyncClient):
    await _seed_articles()
    response = await client.get("/api/content/articles", params={"category": "nutrition"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["category"] == "nutrition"


@pytest.mark.asyncio
async def test_list_articles_by_keyword(client: AsyncClient):
    await _seed_articles()
    response = await client.get("/api/content/articles", params={"keyword": "运动"})
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert "运动" in response.json()["items"][0]["title"]


@pytest.mark.asyncio
async def test_get_article(client: AsyncClient):
    a1_id, _, _ = await _seed_articles()
    response = await client.get(f"/api/content/articles/{a1_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == a1_id
    assert data["title"] == "如何保持健康饮食"
    assert data["view_count"] == 101


@pytest.mark.asyncio
async def test_get_article_not_found(client: AsyncClient):
    response = await client.get("/api/content/articles/99999")
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_article_increments_view_count(client: AsyncClient):
    a1_id, _, _ = await _seed_articles()
    await client.get(f"/api/content/articles/{a1_id}")
    response = await client.get(f"/api/content/articles/{a1_id}")
    assert response.json()["view_count"] == 102


@pytest.mark.asyncio
async def test_create_comment(client: AsyncClient, auth_headers):
    a1_id, _, _ = await _seed_articles()
    response = await client.post("/api/content/comments", json={
        "content_type": "article",
        "content_id": a1_id,
        "content": "写得很好，受益匪浅！",
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "写得很好，受益匪浅！"
    assert data["content_type"] == "article"
    assert data["content_id"] == a1_id
    assert data["parent_id"] is None


@pytest.mark.asyncio
async def test_create_comment_reply(client: AsyncClient, auth_headers):
    a1_id, _, _ = await _seed_articles()
    comment_resp = await client.post("/api/content/comments", json={
        "content_type": "article",
        "content_id": a1_id,
        "content": "第一条评论",
    }, headers=auth_headers)
    parent_id = comment_resp.json()["id"]

    response = await client.post("/api/content/comments", json={
        "content_type": "article",
        "content_id": a1_id,
        "content": "回复第一条",
        "parent_id": parent_id,
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["parent_id"] == parent_id


@pytest.mark.asyncio
async def test_create_comment_unauthorized(client: AsyncClient):
    response = await client.post("/api/content/comments", json={
        "content_type": "article",
        "content_id": 1,
        "content": "test",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_comments(client: AsyncClient, auth_headers):
    a1_id, _, _ = await _seed_articles()
    await client.post("/api/content/comments", json={
        "content_type": "article",
        "content_id": a1_id,
        "content": "评论1",
    }, headers=auth_headers)
    await client.post("/api/content/comments", json={
        "content_type": "article",
        "content_id": a1_id,
        "content": "评论2",
    }, headers=auth_headers)

    response = await client.get("/api/content/comments", params={
        "content_type": "article",
        "content_id": a1_id,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_add_favorite(client: AsyncClient, auth_headers):
    a1_id, _, _ = await _seed_articles()
    response = await client.post("/api/content/favorites", params={
        "content_type": "article",
        "content_id": a1_id,
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["favorited"] is True
    assert "已收藏" in data["message"]


@pytest.mark.asyncio
async def test_toggle_favorite(client: AsyncClient, auth_headers):
    a1_id, _, _ = await _seed_articles()

    await client.post("/api/content/favorites", params={
        "content_type": "article",
        "content_id": a1_id,
    }, headers=auth_headers)

    response = await client.post("/api/content/favorites", params={
        "content_type": "article",
        "content_id": a1_id,
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["favorited"] is False
    assert "取消" in response.json()["message"]


@pytest.mark.asyncio
async def test_list_favorites(client: AsyncClient, auth_headers):
    a1_id, a2_id, _ = await _seed_articles()
    await client.post("/api/content/favorites", params={
        "content_type": "article", "content_id": a1_id,
    }, headers=auth_headers)
    await client.post("/api/content/favorites", params={
        "content_type": "article", "content_id": a2_id,
    }, headers=auth_headers)

    response = await client.get("/api/content/favorites", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_favorite_unauthorized(client: AsyncClient):
    response = await client.post("/api/content/favorites", params={
        "content_type": "article", "content_id": 1,
    })
    assert response.status_code == 401
