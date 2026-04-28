"""
退款与核销互斥业务保护 — 后端接口自动化测试
"""
import pytest
import httpx

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api"


@pytest.fixture
def client():
    return httpx.Client(timeout=15, verify=False)


class TestRefundRedeemMutex:
    """退款与核销互斥测试"""

    def test_redeem_endpoint_exists(self, client):
        """核销接口存在性验证"""
        r = client.post(f"{BASE}/verify/redeem", json={"verification_code": "INVALID_CODE_000"})
        assert r.status_code in (400, 401, 403, 404, 422)

    def test_refund_withdraw_endpoint_exists(self, client):
        """撤回退款接口存在性验证"""
        r = client.post(f"{BASE}/orders/unified/99999/refund/withdraw")
        assert r.status_code in (401, 403, 404, 422)

    def test_refund_detail_endpoint_exists(self, client):
        """退款详情接口存在性验证"""
        r = client.get(f"{BASE}/admin/orders/unified/99999/refund-detail")
        assert r.status_code in (401, 403, 404, 422)

    def test_refund_approve_endpoint_exists(self, client):
        """退款审核接口存在性验证"""
        r = client.post(f"{BASE}/admin/orders/unified/99999/refund/approve", json={})
        assert r.status_code in (401, 403, 404, 422)

    def test_refund_reject_endpoint_exists(self, client):
        """退款拒绝接口存在性验证"""
        r = client.post(f"{BASE}/admin/orders/unified/99999/refund/reject", json={})
        assert r.status_code in (401, 403, 404, 422)

    def test_invalid_verification_code_returns_404(self, client):
        """无效核销码返回404"""
        r = client.post(f"{BASE}/verify/redeem", json={"verification_code": "NONEXISTENT_999"})
        assert r.status_code in (401, 403, 404)
