"""[客户端订单顾客操作鉴权误判 Bug 修复 v1.0] 回归测试

覆盖范围
========
A. utils.client_source 新增 customer 客户端家族
   - CLIENT_H5_USER / CLIENT_MINIPROGRAM_USER / CLIENT_APP_USER 常量
   - CUSTOMER_CLIENTS 集合
   - is_customer_client() 判定函数
   - require_customer_client_session() 依赖项放行/拦截

B. 订单顾客专属接口的「客户端会话强校验」（统一的 8 个接口）
   接口路径前缀：/api/orders/unified
   - POST /                   下单
   - POST /{id}/pay           支付
   - POST /{id}/appointment   修改/设置预约（本次 Bug 主犯）
   - POST /{id}/cancel        取消订单
   - POST /{id}/confirm       确认收货
   - POST /{id}/review        评价订单
   - POST /{id}/refund        申请退款
   - POST /{id}/refund/withdraw 撤回退款
   - POST /{id}/confirm-free  0 元单确认（同源加固）

   测试矩阵：
   - 客户端家族（h5-user / miniprogram-user / app-user）→ 不返回 403（可能 4xx 业务错，但绝不能是鉴权 403）
   - 商家端家族（h5-mobile / verify-miniprogram / pc-web）→ 返回 403 + CUSTOMER_FORBIDDEN_DETAIL
   - 不带 Client-Type Header（unknown 兜底）→ 返回 403 + CUSTOMER_FORBIDDEN_DETAIL
   - 商家兼顾客（users.role=merchant）+ 客户端 Header → 不返回 403（核心修复目标）
"""
from __future__ import annotations

from typing import Optional
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import User, UserRole
from app.utils.client_source import (
    CLIENT_APP_USER,
    CLIENT_H5_MOBILE,
    CLIENT_H5_USER,
    CLIENT_MINIPROGRAM_USER,
    CLIENT_PC_WEB,
    CLIENT_VERIFY_MINIPROGRAM,
    CUSTOMER_CLIENTS,
    CUSTOMER_FORBIDDEN_DETAIL,
    is_customer_client,
    require_customer_client_session,
)


# ────────── A. 单元测试：customer 客户端家族 ──────────


def _make_request(headers: Optional[dict] = None):
    req = MagicMock()
    h = {k.lower(): v for k, v in (headers or {}).items()}
    req.headers = MagicMock()
    req.headers.get = lambda name, default=None: (
        headers.get(name)
        if headers and name in headers
        else h.get(name.lower(), default)
    )
    return req


class TestCustomerClientConstants:
    def test_customer_clients_set_size(self):
        assert len(CUSTOMER_CLIENTS) == 3

    def test_customer_clients_members(self):
        assert CLIENT_H5_USER in CUSTOMER_CLIENTS
        assert CLIENT_MINIPROGRAM_USER in CUSTOMER_CLIENTS
        assert CLIENT_APP_USER in CUSTOMER_CLIENTS

    def test_customer_clients_excludes_merchant_side(self):
        assert CLIENT_H5_MOBILE not in CUSTOMER_CLIENTS
        assert CLIENT_VERIFY_MINIPROGRAM not in CUSTOMER_CLIENTS
        assert CLIENT_PC_WEB not in CUSTOMER_CLIENTS


class TestIsCustomerClient:
    @pytest.mark.parametrize("ctype", [CLIENT_H5_USER, CLIENT_MINIPROGRAM_USER, CLIENT_APP_USER])
    def test_passes_for_customer_clients(self, ctype):
        assert is_customer_client(ctype) is True

    @pytest.mark.parametrize(
        "ctype",
        [
            CLIENT_H5_MOBILE,
            CLIENT_VERIFY_MINIPROGRAM,
            CLIENT_PC_WEB,
            "unknown",
            "",
            None,
        ],
    )
    def test_rejects_non_customer(self, ctype):
        assert is_customer_client(ctype) is False


class TestRequireCustomerClientSession:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("ctype", [CLIENT_H5_USER, CLIENT_MINIPROGRAM_USER, CLIENT_APP_USER])
    async def test_pass_for_customer_clients(self, ctype):
        req = _make_request({"Client-Type": ctype})
        result = await require_customer_client_session(req)
        assert result == ctype

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "ctype",
        [CLIENT_H5_MOBILE, CLIENT_VERIFY_MINIPROGRAM, CLIENT_PC_WEB],
    )
    async def test_reject_merchant_side(self, ctype):
        req = _make_request({"Client-Type": ctype})
        with pytest.raises(HTTPException) as exc:
            await require_customer_client_session(req)
        assert exc.value.status_code == 403
        assert exc.value.detail == CUSTOMER_FORBIDDEN_DETAIL

    @pytest.mark.asyncio
    async def test_reject_unknown(self):
        # 不带任何 Header / UA → unknown
        req = _make_request({})
        with pytest.raises(HTTPException) as exc:
            await require_customer_client_session(req)
        assert exc.value.status_code == 403
        assert exc.value.detail == CUSTOMER_FORBIDDEN_DETAIL

    @pytest.mark.asyncio
    async def test_x_client_type_header_works(self):
        req = _make_request({"X-Client-Type": CLIENT_APP_USER})
        result = await require_customer_client_session(req)
        assert result == CLIENT_APP_USER


# ────────── B. 集成测试：8 个订单顾客接口的鉴权拦截 ──────────


@pytest_asyncio.fixture
async def merchant_user_token(client: AsyncClient):
    """构造一个 users.role=merchant 的用户（"商家兼顾客"场景的核心人物）。"""
    from app.core.database import get_db
    from app.core.security import get_password_hash, create_access_token

    # 通过依赖覆盖直接拿到测试 db session
    from app.main import app as _app
    db_dep = _app.dependency_overrides[get_db]
    async for db in db_dep():  # type: ignore[union-attr]
        u = User(
            phone="13700000999",
            password_hash=get_password_hash("merchant123"),
            nickname="商家兼顾客",
            role=UserRole.merchant,
        )
        db.add(u)
        await db.flush()
        await db.refresh(u)
        token = create_access_token({"sub": str(u.id)})
        await db.commit()
        return token
    raise RuntimeError("could not bootstrap merchant user")


# 9 个收口接口的 (method, path_template) 列表。
# path_template 中 {id} 会被替换为占位订单 id（即使订单不存在也不要紧，
# 我们只关心 403 是否在「订单查询前」就被 require_customer_client_session 拦下）。
_ORDER_CUSTOMER_ENDPOINTS = [
    ("POST", "/api/orders/unified", {"items": []}),
    ("POST", "/api/orders/unified/999999/pay", {"payment_method": "wechat"}),
    ("POST", "/api/orders/unified/999999/appointment", {"appointment_time": "2099-01-01T10:00:00"}),
    ("POST", "/api/orders/unified/999999/cancel", {"cancel_reason": "test"}),
    ("POST", "/api/orders/unified/999999/confirm", None),
    ("POST", "/api/orders/unified/999999/review", {"rating": 5, "content": "ok"}),
    ("POST", "/api/orders/unified/999999/refund", {"reason": "test"}),
    ("POST", "/api/orders/unified/999999/refund/withdraw", None),
    ("POST", "/api/orders/unified/999999/confirm-free", {"channel_code": None}),
]


async def _call_endpoint(client: AsyncClient, method: str, path: str, body, headers: dict):
    if method == "POST":
        if body is None:
            return await client.post(path, headers=headers)
        return await client.post(path, json=body, headers=headers)
    raise NotImplementedError(method)


class TestOrderCustomerEndpointsForbidMerchantSide:
    """所有 8(+1) 个接口在「商家端来源」+「任何身份」下必须 403。"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path,body", _ORDER_CUSTOMER_ENDPOINTS)
    @pytest.mark.parametrize("merchant_ctype", [CLIENT_H5_MOBILE, CLIENT_VERIFY_MINIPROGRAM, CLIENT_PC_WEB])
    async def test_merchant_client_blocked(
        self, client, user_token, method, path, body, merchant_ctype
    ):
        headers = {
            "Authorization": f"Bearer {user_token}",
            "Client-Type": merchant_ctype,
        }
        resp = await _call_endpoint(client, method, path, body, headers)
        assert resp.status_code == 403, (
            f"{method} {path} 在 {merchant_ctype} 来源下应返回 403，实际 {resp.status_code}: {resp.text}"
        )
        assert CUSTOMER_FORBIDDEN_DETAIL in resp.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path,body", _ORDER_CUSTOMER_ENDPOINTS)
    async def test_no_client_type_header_blocked(
        self, client, user_token, method, path, body
    ):
        # 不带 Client-Type Header（unknown 兜底）→ 应被拦
        headers = {"Authorization": f"Bearer {user_token}"}
        resp = await _call_endpoint(client, method, path, body, headers)
        assert resp.status_code == 403, (
            f"{method} {path} 不带 Client-Type 应返回 403，实际 {resp.status_code}: {resp.text}"
        )
        assert CUSTOMER_FORBIDDEN_DETAIL in resp.text


class TestOrderCustomerEndpointsAllowCustomerSide:
    """客户端来源（h5-user / miniprogram-user / app-user）必须不被 403 拦截。

    注：因为占位订单 999999 不存在，预期会返回 404 / 400 业务错误，
    但绝不能是 403——这正是本次 Bug 修复的核心目标。
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path,body", _ORDER_CUSTOMER_ENDPOINTS)
    @pytest.mark.parametrize(
        "customer_ctype",
        [CLIENT_H5_USER, CLIENT_MINIPROGRAM_USER, CLIENT_APP_USER],
    )
    async def test_customer_client_not_403(
        self, client, user_token, method, path, body, customer_ctype
    ):
        headers = {
            "Authorization": f"Bearer {user_token}",
            "Client-Type": customer_ctype,
        }
        resp = await _call_endpoint(client, method, path, body, headers)
        # 关键断言：不能是 403（这是 Bug 主症状）
        # 允许的状态码：200 / 400 / 404 / 422 等业务/参数/订单不存在错误
        assert resp.status_code != 403, (
            f"{method} {path} 在客户端来源 {customer_ctype} 下不应被 403 拦截！"
            f" 实际 {resp.status_code}: {resp.text}"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path,body", _ORDER_CUSTOMER_ENDPOINTS)
    @pytest.mark.parametrize(
        "customer_ctype",
        [CLIENT_H5_USER, CLIENT_MINIPROGRAM_USER, CLIENT_APP_USER],
    )
    async def test_merchant_role_user_in_customer_client_not_403(
        self, client, merchant_user_token, method, path, body, customer_ctype
    ):
        """[本次 Bug 主犯场景] users.role=merchant 的用户在客户端登录后调用顾客接口。

        修复前：所有 8(+1) 个接口（其中 appointment 是 Bug 主犯）会因 role=merchant
        被一刀切（appointment 接口返回 403 "无操作权限"）。
        修复后：因 Client-Type=h5-user/miniprogram-user/app-user，require_customer_client_session
        放行；不应返回 403。
        """
        headers = {
            "Authorization": f"Bearer {merchant_user_token}",
            "Client-Type": customer_ctype,
        }
        resp = await _call_endpoint(client, method, path, body, headers)
        assert resp.status_code != 403, (
            f"[Bug 主犯回归] role=merchant + {customer_ctype} 在 {method} {path} 不应被 403。"
            f" 实际 {resp.status_code}: {resp.text}"
        )


class TestNoStaleRoleCheckRemainsInAppointment:
    """显式回归：旧版 PRD-03 在 set_order_appointment 顶部硬写的 role 一刀切代码块
    （`if str(role_val) != "user": raise 403 "无操作权限：改期权仅限客户端,商家/平台无权调用"`）
    必须已被移除。
    """

    @pytest.mark.asyncio
    async def test_old_role_check_message_no_longer_returned(
        self, client, merchant_user_token
    ):
        """商家身份 + 客户端 Header 调用改期接口，不应再看到旧版"无操作权限"文案。"""
        headers = {
            "Authorization": f"Bearer {merchant_user_token}",
            "Client-Type": CLIENT_H5_USER,
        }
        resp = await client.post(
            "/api/orders/unified/999999/appointment",
            json={"appointment_time": "2099-01-01T10:00:00"},
            headers=headers,
        )
        # 不应是 403，且不应包含旧版文案
        assert resp.status_code != 403
        assert "改期权仅限客户端" not in resp.text
