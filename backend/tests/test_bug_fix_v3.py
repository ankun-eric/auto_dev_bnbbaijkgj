"""Bug fix v3 regression tests.

Covers:
- BUG2-A: Coupon NULL valid_end should be treated as long-term valid
  and surface in /api/coupons/mine?tab=unused&exclude_expired=true.
- BUG3-B: /api/points/tasks must always return 200 with an "items" key.
- /api/points/summary must return 200.
- BUG4: chat session creation accepts new tcm_tongue / tcm_face session_type values.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.models import Coupon, CouponStatus, CouponType, User
from tests.conftest import test_session


@pytest_asyncio.fixture
async def long_term_coupon():
    """Create a Coupon with valid_end=None (treated as long-term valid)."""
    async with test_session() as session:
        coupon = Coupon(
            name="测试长期券",
            type=CouponType.full_reduction,
            condition_amount=100,
            discount_value=10,
            total_count=100,
            claimed_count=0,
            valid_start=None,
            valid_end=None,
            status=CouponStatus.active,
        )
        session.add(coupon)
        await session.commit()
        await session.refresh(coupon)
        return coupon.id


@pytest.mark.asyncio
async def test_coupon_with_null_valid_end_appears_in_unused_tab(
    client: AsyncClient, auth_headers, long_term_coupon
):
    coupon_id = long_term_coupon

    claim_resp = await client.post(
        "/api/coupons/claim",
        json={"coupon_id": coupon_id},
        headers=auth_headers,
    )
    assert claim_resp.status_code == 200, claim_resp.text

    resp = await client.get(
        "/api/coupons/mine",
        params={"tab": "unused", "exclude_expired": "true"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    coupon_ids = [item.get("coupon_id") for item in data["items"]]
    assert coupon_id in coupon_ids, (
        f"NULL-valid_end coupon {coupon_id} should appear with exclude_expired=true, "
        f"got items={data['items']}"
    )


@pytest.mark.asyncio
async def test_coupon_with_null_valid_end_in_available_list(
    client: AsyncClient, auth_headers, long_term_coupon
):
    coupon_id = long_term_coupon
    resp = await client.get("/api/coupons/available", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    available_ids = [item.get("id") for item in data.get("items", [])]
    assert coupon_id in available_ids


@pytest.mark.asyncio
async def test_points_tasks_returns_200_always(client: AsyncClient, auth_headers):
    resp = await client.get("/api/points/tasks", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_points_summary_returns_200(client: AsyncClient, auth_headers):
    resp = await client.get("/api/points/summary", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "total_points" in data
    assert "today_earned_points" in data
    assert "signed_today" in data
    assert "sign_days" in data


@pytest.mark.asyncio
async def test_chat_session_create_with_tcm_tongue(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/chat/sessions",
        json={"session_type": "tcm_tongue", "title": "舌诊"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["session_type"] == "tcm_tongue"
    assert data["title"] == "舌诊"
    assert "id" in data


@pytest.mark.asyncio
async def test_chat_session_create_with_tcm_face(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/chat/sessions",
        json={"session_type": "tcm_face", "title": "面诊"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["session_type"] == "tcm_face"
    assert data["title"] == "面诊"
    assert "id" in data
