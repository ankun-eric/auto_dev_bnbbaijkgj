"""
测试家人邀请二维码修复 - 确保二维码URL指向授权页而非扫码中转页

Bug: qr_content_url 原先指向 /scan?type=family_invite&code=xxx（扫码中转页），导致重复扫码。
Fix: qr_content_url 改为 /family-auth?code=xxx，scan API 的 redirect_url 也改为 /family-auth?code=xxx。

本测试文件通过本地 ASGI 客户端验证修复后的代码逻辑。
"""
import pytest
from httpx import AsyncClient


@pytest.fixture
async def _member_id(client: AsyncClient, auth_headers: dict) -> int:
    resp = await client.post("/api/family/members", headers=auth_headers, json={
        "nickname": "测试家人_QR",
        "relationship_type": "父亲",
        "gender": "male",
    })
    assert resp.status_code == 200
    return resp.json()["id"]


@pytest.fixture
async def invitation_data(client: AsyncClient, auth_headers: dict, _member_id: int) -> dict:
    resp = await client.post(
        "/api/family/invitation",
        headers=auth_headers,
        json={"member_id": _member_id},
    )
    assert resp.status_code == 200, f"Create invitation failed: {resp.status_code} {resp.text}"
    return resp.json()


class TestQRContentURL:
    """验证 POST /api/family/invitation 返回的 qr_content_url 格式正确"""

    async def test_create_invitation_qr_content_url_format(
        self, client: AsyncClient, invitation_data: dict
    ):
        """qr_content_url 应包含 /family-auth?code= 而非 /scan?type="""
        qr_url = invitation_data["qr_content_url"]
        assert "/family-auth?code=" in qr_url, (
            f"qr_content_url should contain '/family-auth?code=', got: {qr_url}"
        )

    async def test_create_invitation_qr_content_url_not_scan(
        self, client: AsyncClient, invitation_data: dict
    ):
        """qr_content_url 不应包含 /scan"""
        qr_url = invitation_data["qr_content_url"]
        assert "/scan" not in qr_url, (
            f"qr_content_url should NOT contain '/scan', got: {qr_url}"
        )

    async def test_qr_content_url_contains_full_domain(
        self, client: AsyncClient, invitation_data: dict
    ):
        """qr_content_url 应包含完整域名"""
        qr_url = invitation_data["qr_content_url"]
        assert qr_url.startswith("https://"), (
            f"qr_content_url should start with 'https://', got: {qr_url}"
        )
        assert "newbb.bangbangvip.com" in qr_url, (
            f"qr_content_url should contain full domain, got: {qr_url}"
        )


class TestScanAPIRedirect:
    """验证 GET /api/scan 的 redirect_url 格式正确"""

    async def test_scan_api_redirect_url_format(
        self, client: AsyncClient, invitation_data: dict
    ):
        """redirect_url 应包含 /family-auth?code="""
        code = invitation_data["invite_code"]
        resp = await client.get("/api/scan", params={"type": "family_invite", "code": code})
        assert resp.status_code == 200, f"Scan API failed: {resp.status_code} {resp.text}"
        body = resp.json()
        redirect_url = body["redirect_url"]
        assert "/family-auth?code=" in redirect_url, (
            f"redirect_url should contain '/family-auth?code=', got: {redirect_url}"
        )

    async def test_scan_api_redirect_url_not_old_format(
        self, client: AsyncClient, invitation_data: dict
    ):
        """redirect_url 不应包含 /family-invite-confirm"""
        code = invitation_data["invite_code"]
        resp = await client.get("/api/scan", params={"type": "family_invite", "code": code})
        assert resp.status_code == 200
        body = resp.json()
        redirect_url = body["redirect_url"]
        assert "/family-invite-confirm" not in redirect_url, (
            f"redirect_url should NOT contain '/family-invite-confirm', got: {redirect_url}"
        )

    async def test_scan_api_invalid_type(self, client: AsyncClient):
        """不支持的扫码类型应返回 400"""
        resp = await client.get("/api/scan", params={"type": "unknown", "code": "xxx"})
        assert resp.status_code == 400, (
            f"Expected 400 for invalid scan type, got: {resp.status_code}"
        )

    async def test_scan_api_missing_params(self, client: AsyncClient):
        """缺少参数时应返回 422"""
        resp = await client.get("/api/scan")
        assert resp.status_code == 422, (
            f"Expected 422 for missing params, got: {resp.status_code}"
        )


class TestInvitationDetail:
    """验证邀请详情和异常邀请码的处理"""

    async def test_invitation_get_details(
        self, client: AsyncClient, invitation_data: dict
    ):
        """GET /api/family/invitation/{code} 应返回正确的邀请详情"""
        code = invitation_data["invite_code"]
        resp = await client.get(f"/api/family/invitation/{code}")
        assert resp.status_code == 200, f"Get detail failed: {resp.status_code} {resp.text}"
        body = resp.json()
        assert body["invite_code"] == code
        assert body["status"] in ("pending", "expired", "accepted", "cancelled")
        assert "inviter_nickname" in body
        assert "member_nickname" in body
        assert "expires_at" in body

    async def test_invitation_expired_code(self, client: AsyncClient):
        """使用不存在的邀请码应返回 404"""
        resp = await client.get("/api/family/invitation/nonexistent_code_abc123")
        assert resp.status_code == 404, (
            f"Expected 404 for invalid invite code, got: {resp.status_code}"
        )
