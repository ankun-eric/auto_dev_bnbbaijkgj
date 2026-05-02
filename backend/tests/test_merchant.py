import pytest
from httpx import AsyncClient

from app.models.models import MerchantCategory, ServiceCategory, ServiceItem
from tests.conftest import test_session


async def _ensure_default_category() -> int:
    """[2026-05-01] 确保商家分类存在以满足 create_store 必填要求。"""
    async with test_session() as db:
        from sqlalchemy import select
        res = await db.execute(select(MerchantCategory).where(MerchantCategory.code == "self_store"))
        cat = res.scalar_one_or_none()
        if cat:
            return cat.id
        cat = MerchantCategory(code="self_store", name="自营门店", sort=0, status="active")
        db.add(cat)
        await db.commit()
        await db.refresh(cat)
        return cat.id


async def _create_store(client: AsyncClient, admin_headers, store_code: str = "STORE001") -> int:
    # [2026-05-01 门店地图能力 PRD v1.0] 新建必传经纬度 + category_id
    cat_id = await _ensure_default_category()
    response = await client.post(
        "/api/admin/merchant/stores",
        json={
            "store_name": "测试门店",
            "store_code": store_code,
            "category_id": cat_id,
            "contact_name": "门店店长",
            "contact_phone": "13800009999",
            "address": "测试地址",
            "lat": 23.1234567,
            "lng": 113.4567890,
            "status": "active",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def _create_service_item() -> int:
    from tests.conftest import test_session

    async with test_session() as db:
        category = ServiceCategory(name="商家测试分类", status="active", sort_order=1)
        db.add(category)
        await db.flush()
        item = ServiceItem(
            category_id=category.id,
            name="到店服务",
            description="用于商家核销测试",
            price=99.00,
            original_price=129.00,
            service_type="offline",
            stock=10,
            sales_count=0,
            status="active",
        )
        db.add(item)
        await db.commit()
        return item.id


@pytest.mark.asyncio
async def test_admin_can_create_dual_identity_account_and_login_context(
    client: AsyncClient,
    admin_headers,
    latest_sms_code,
):
    store_id = await _create_store(client, admin_headers, "STORE100")
    create_resp = await client.post(
        "/api/admin/merchant/accounts",
        json={
            "phone": "13800110011",
            "password": "test1234",
            "user_nickname": "双身份用户",
            "enable_user_identity": True,
            "merchant_identity_type": "staff",
            "merchant_nickname": "商家小李",
            "status": "active",
            "store_permissions": [
                {
                    "store_id": store_id,
                    "module_codes": ["dashboard", "verify", "records", "messages", "profile"],
                }
            ],
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 200

    code_resp = await client.post(
        "/api/auth/sms-code",
        json={"phone": "13800110011", "type": "login"},
    )
    assert code_resp.status_code == 200

    login_resp = await client.post(
        "/api/auth/sms-login",
        json={"phone": "13800110011", "code": await latest_sms_code("13800110011")},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["session_context"]["can_access_user"] is True
    assert data["session_context"]["can_access_merchant"] is True
    assert data["session_context"]["is_dual_identity"] is True
    assert data["session_context"]["default_entry"] == "select_role"
    assert data["merchant_profile"]["nickname"] == "商家小李"


@pytest.mark.asyncio
async def test_merchant_can_verify_order_and_query_records(
    client: AsyncClient,
    admin_headers,
    latest_sms_code,
):
    store_id = await _create_store(client, admin_headers, "STORE200")
    merchant_resp = await client.post(
        "/api/admin/merchant/accounts",
        json={
            "phone": "13800220022",
            "password": "test1234",
            "user_nickname": "核销员工",
            "enable_user_identity": False,
            "merchant_identity_type": "staff",
            "merchant_nickname": "核销专员",
            "status": "active",
            "store_permissions": [
                {
                    "store_id": store_id,
                    "module_codes": ["dashboard", "verify", "records", "messages", "profile"],
                }
            ],
        },
        headers=admin_headers,
    )
    assert merchant_resp.status_code == 200

    sms_code_resp = await client.post(
        "/api/auth/sms-code",
        json={"phone": "13800220022", "type": "login"},
    )
    merchant_login_resp = await client.post(
        "/api/auth/sms-login",
        json={"phone": "13800220022", "code": await latest_sms_code("13800220022")},
    )
    assert merchant_login_resp.status_code == 200
    merchant_headers = {"Authorization": f"Bearer {merchant_login_resp.json()['access_token']}"}
    assert merchant_login_resp.json()["session_context"]["can_access_user"] is False
    assert merchant_login_resp.json()["session_context"]["default_entry"] == "merchant"

    service_item_id = await _create_service_item()
    await client.post(
        "/api/auth/register",
        json={
            "phone": "13800330033",
            "password": "user12345",
            "nickname": "下单用户",
        },
    )
    user_login_resp = await client.post(
        "/api/auth/login",
        json={"phone": "13800330033", "password": "user12345"},
    )
    user_headers = {"Authorization": f"Bearer {user_login_resp.json()['access_token']}"}

    create_order_resp = await client.post(
        "/api/orders",
        json={
            "service_item_id": service_item_id,
            "quantity": 1,
            "payment_method": "wechat",
        },
        headers=user_headers,
    )
    assert create_order_resp.status_code == 200
    order_data = create_order_resp.json()

    verify_code_resp = await client.get(
        f"/api/merchant/orders/verify-code/{order_data['verification_code']}",
        params={"store_id": store_id},
        headers=merchant_headers,
    )
    assert verify_code_resp.status_code == 200
    assert verify_code_resp.json()["status"] == "pending"

    verify_resp = await client.post(
        f"/api/merchant/orders/{order_data['id']}/verify",
        json={"store_id": store_id, "code": order_data["verification_code"]},
        headers=merchant_headers,
    )
    assert verify_resp.status_code == 200

    records_resp = await client.get(
        "/api/merchant/orders/records",
        params={"store_id": store_id},
        headers=merchant_headers,
    )
    assert records_resp.status_code == 200
    assert records_resp.json()["total"] == 1
    assert records_resp.json()["items"][0]["order_no"] == order_data["order_no"]
