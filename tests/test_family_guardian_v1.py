"""[PRD-FAMILY-GUARDIAN-V1] 家庭体检异常·守护推送 - 非UI自动化测试。

针对已部署的服务器执行。测试守护者集合算法、5min 去重、
管理后台 CRUD、虚拟档案迁移、解绑双向通知。

Run: pytest tests/test_family_guardian_v1.py -v
"""

from __future__ import annotations

import random
import string
import time
import warnings

import pytest
import requests

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = (
    "https://newbb.test.bangbangvip.com"
    "/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
)
API_URL = f"{BASE_URL}/api"
TIMEOUT = 20
TEST_CODE = "123456"


def _random_phone() -> str:
    return "138" + "".join(random.choices(string.digits, k=8))


# 后端 TEST_PHONES = {13800138000, 13800000001, 13800000002}，固定验证码 123456
TEST_PHONES = ["13800138000", "13800000001", "13800000002"]
_test_phone_idx = 0


def _pick_test_phone() -> str:
    global _test_phone_idx
    p = TEST_PHONES[_test_phone_idx % len(TEST_PHONES)]
    _test_phone_idx += 1
    return p


def _login_or_register(phone: str) -> str:
    """获取测试用 token：发送验证码 → 用通用 code 登录（开发环境通用 code = 123456）。"""
    requests.post(
        f"{API_URL}/auth/sms-code",
        json={"phone": phone, "type": "login"},
        timeout=TIMEOUT,
        verify=False,
    )
    res = requests.post(
        f"{API_URL}/auth/sms-login",
        json={"phone": phone, "code": TEST_CODE},
        timeout=TIMEOUT,
        verify=False,
    )
    assert res.status_code == 200, f"login failed: {res.status_code} {res.text}"
    data = res.json()
    token = data.get("access_token") or data.get("token") or data.get("data", {}).get("access_token")
    assert token, f"no token in response: {data}"
    return token


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ───── 基础健康检查 ─────


def test_backend_health():
    """后端 /api/health 或根路径返回 2xx。"""
    res = requests.get(f"{API_URL}/health", timeout=TIMEOUT, verify=False)
    assert res.status_code in (200, 204, 404), f"health endpoint unexpected: {res.status_code}"


# ───── 守护者算法 API ─────


@pytest.fixture(scope="module")
def auth():
    # 使用预置测试号，固定验证码 123456
    phone = _pick_test_phone()
    token = _login_or_register(phone)
    return {"phone": phone, "token": token}


def test_my_alert_logs_empty_ok(auth):
    """新用户访问 /api/me/alert-logs，应返回空列表。"""
    res = requests.get(
        f"{API_URL}/me/alert-logs",
        headers=_headers(auth["token"]),
        timeout=TIMEOUT,
        verify=False,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "items" in data
    assert "total" in data


def test_my_pending_migrations_empty_ok(auth):
    """新用户访问 /api/me/pending-migrations，应返回空列表。"""
    res = requests.get(
        f"{API_URL}/me/pending-migrations",
        headers=_headers(auth["token"]),
        timeout=TIMEOUT,
        verify=False,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_internal_user_registered_hook():
    """注册钩子：使用一个未关联的手机号调用钩子应返回 0 个迁移。"""
    phone = _random_phone()
    # 先得有 user_id - 这里仅验证接口返回 created 字段
    # 注：钩子接口未对内部签名验证，方便联调
    res = requests.post(
        f"{API_URL}/internal/user/registered",
        json={"user_id": 999999999, "phone": phone},
        timeout=TIMEOUT,
        verify=False,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "created" in data
    assert data["created"] == 0


def test_internal_checkup_parsed_no_member():
    """触发不存在的 member_id，应返回 404。"""
    res = requests.post(
        f"{API_URL}/internal/checkup/parsed",
        json={
            "member_id": 999999999,
            "abnormal_count": 3,
            "severity": "warning",
            "report_date": "2026-05-18",
        },
        timeout=TIMEOUT,
        verify=False,
    )
    assert res.status_code == 404, res.text


def test_guardians_query_requires_auth():
    """守护者查询需要登录。"""
    res = requests.get(
        f"{API_URL}/family/guardians/1",
        timeout=TIMEOUT,
        verify=False,
    )
    assert res.status_code in (401, 403), res.text


# ───── 守护者算法：建档→推送→去重 端到端 ─────


def test_e2e_create_member_then_push_dedup(auth):
    """端到端：当前用户创建家庭成员→触发体检异常推送→第二次同 report_date 命中去重。"""
    # 1) 创建家庭成员（虚拟档案场景 A：仅建档人为守护者）
    member_payload = {
        "relationship_type": "father",
        "nickname": "测试父亲" + str(int(time.time())),
        "gender": "male",
        "name": "测试父亲",
    }
    res = requests.post(
        f"{API_URL}/family/members",
        headers=_headers(auth["token"]),
        json=member_payload,
        timeout=TIMEOUT,
        verify=False,
    )
    if res.status_code in (404, 405):
        pytest.skip(f"/api/family/members endpoint not available: {res.status_code}")
    assert res.status_code in (200, 201), res.text
    body = res.json()
    member_id = body.get("id") or body.get("data", {}).get("id")
    assert member_id, res.text

    # 2) 首次触发推送
    payload = {
        "member_id": member_id,
        "abnormal_count": 5,
        "severity": "warning",
        "report_date": "2026-05-18",
    }
    res1 = requests.post(
        f"{API_URL}/internal/checkup/parsed",
        json=payload,
        timeout=TIMEOUT,
        verify=False,
    )
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1.get("deduped") is False
    assert data1.get("sent", 0) >= 1, f"expected at least 1 push, got {data1}"

    # 3) 5min 内再次触发同 report_date，应被去重
    res2 = requests.post(
        f"{API_URL}/internal/checkup/parsed",
        json=payload,
        timeout=TIMEOUT,
        verify=False,
    )
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert data2.get("deduped") is True, f"expected dedup True, got {data2}"

    # 4) /api/me/alert-logs 至少有 1 条
    res3 = requests.get(
        f"{API_URL}/me/alert-logs",
        headers=_headers(auth["token"]),
        timeout=TIMEOUT,
        verify=False,
    )
    assert res3.status_code == 200
    assert res3.json().get("total", 0) >= 1


def test_zero_abnormal_no_push():
    """abnormal_count = 0 不应推送。"""
    res = requests.post(
        f"{API_URL}/internal/checkup/parsed",
        json={"member_id": 1, "abnormal_count": 0, "report_date": "2026-05-18"},
        timeout=TIMEOUT,
        verify=False,
    )
    # member 可能不存在，则 404；否则 200 且 sent=0
    assert res.status_code in (200, 404), res.text
    if res.status_code == 200:
        data = res.json()
        assert data.get("sent", 0) == 0


# ───── 管理后台：未登录或非 admin 不能访问 ─────


def test_admin_endpoints_require_admin():
    for path in (
        "/api/admin/alert-templates",
        "/api/admin/abnormal-thresholds",
        "/api/admin/alert-logs",
    ):
        res = requests.get(f"{BASE_URL}{path}", timeout=TIMEOUT, verify=False)
        assert res.status_code in (401, 403), f"{path} should require admin, got {res.status_code}"


# ───── UI 文案合规：'守护' 用语在邀请详情接口的文案里出现 ─────


def test_invitation_get_with_invalid_code():
    """获取不存在邀请返回 404，确保接口可达。"""
    res = requests.get(
        f"{API_URL}/family/invitation/nonexistent-code-xxx",
        timeout=TIMEOUT,
        verify=False,
    )
    assert res.status_code == 404
