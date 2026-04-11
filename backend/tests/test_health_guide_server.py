"""
Server-side integration tests for health-guide page validation fix.
Runs against the live deployed environment via HTTPS.
"""

import random
import string

import httpx
import pytest

BASE_URL = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_URL = f"{BASE_URL}/api"

_PHONE_SUFFIX = "".join(random.choices(string.digits, k=8))
TEST_PHONE = f"139{_PHONE_SUFFIX}"
TEST_PASSWORD = "TestPass1234"


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=API_URL, verify=False, timeout=30) as c:
        yield c


@pytest.fixture(scope="module")
def page_client():
    with httpx.Client(verify=False, timeout=30, follow_redirects=True) as c:
        yield c


@pytest.fixture(scope="module")
def auth_token(client: httpx.Client):
    resp = client.post("/auth/register", json={
        "phone": TEST_PHONE,
        "password": TEST_PASSWORD,
        "nickname": f"健康测试{_PHONE_SUFFIX}",
    })
    if resp.status_code == 400 and "已注册" in resp.text:
        resp = client.post("/auth/login", json={
            "phone": TEST_PHONE,
            "password": TEST_PASSWORD,
        })
    assert resp.status_code == 200, f"Auth failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token: str):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def self_member_id(client: httpx.Client, auth_headers: dict):
    resp = client.get("/family/members", headers=auth_headers)
    assert resp.status_code == 200, f"Failed to get family members: {resp.text}"
    items = resp.json()["items"]
    for m in items:
        if m.get("is_self"):
            return m["id"]
    pytest.fail("No is_self=True member found in family members list")


class TestHealthProfileApiAlive:
    def test_health_profile_api_alive(self, client: httpx.Client):
        """GET /api/health returns 200."""
        resp = client.get("/health")
        assert resp.status_code == 200, (
            f"健康检查API不可用: status={resp.status_code}, body={resp.text}"
        )


class TestHealthGuidePageAccessible:
    def test_health_guide_page_accessible(self, page_client: httpx.Client):
        """GET /health-guide returns 200."""
        resp = page_client.get(f"{BASE_URL}/health-guide")
        assert resp.status_code == 200, (
            f"健康引导页不可访问: status={resp.status_code}"
        )


class TestRegisterAndLogin:
    def test_register_and_login(self, client: httpx.Client):
        """Register a fresh user and login to get token."""
        suffix = "".join(random.choices(string.digits, k=8))
        phone = f"138{suffix}"
        password = "RegTest999"

        reg_resp = client.post("/auth/register", json={
            "phone": phone,
            "password": password,
            "nickname": f"注册测试{suffix}",
        })
        if reg_resp.status_code == 400 and "已注册" in reg_resp.text:
            pass
        else:
            assert reg_resp.status_code == 200, (
                f"注册失败: status={reg_resp.status_code}, body={reg_resp.text}"
            )

        login_resp = client.post("/auth/login", json={
            "phone": phone,
            "password": password,
        })
        assert login_resp.status_code == 200, (
            f"登录失败: status={login_resp.status_code}, body={login_resp.text}"
        )
        data = login_resp.json()
        assert "access_token" in data, f"响应缺少access_token: {data}"


class TestUpdateMemberProfileWithAllRequiredFields:
    def test_update_member_profile_with_all_required_fields(
        self, client: httpx.Client, auth_headers: dict, self_member_id: int
    ):
        """PUT /api/health/profile/member/{id} with name, gender, birthday should succeed."""
        resp = client.put(
            f"/health/profile/member/{self_member_id}",
            json={
                "name": "测试全字段",
                "gender": "male",
                "birthday": "1990-05-20",
                "height": 175.0,
                "weight": 68.5,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, (
            f"带全部必填字段更新档案失败: status={resp.status_code}, body={resp.text}"
        )
        data = resp.json()
        assert data.get("name") == "测试全字段"
        assert data.get("gender") == "male"
        assert data.get("birthday") == "1990-05-20"


class TestUpdateMemberProfilePartialData:
    def test_update_member_profile_partial_data(
        self, client: httpx.Client, auth_headers: dict, self_member_id: int
    ):
        """PUT /api/health/profile/member/{id} with only height & weight should succeed (backend has no required-field validation)."""
        resp = client.put(
            f"/health/profile/member/{self_member_id}",
            json={
                "height": 180.0,
                "weight": 72.0,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, (
            f"部分数据更新档案失败: status={resp.status_code}, body={resp.text}"
        )
        data = resp.json()
        assert data.get("height") == 180.0
        assert data.get("weight") == 72.0


class TestFrontendHealthGuideHtmlContainsValidationText:
    def test_frontend_health_guide_html_contains_validation_text(
        self, page_client: httpx.Client
    ):
        """The deployed health-guide page JS bundle should contain validation prompt text, confirming the fix is live."""
        import re

        html_resp = page_client.get(f"{BASE_URL}/health-guide")
        assert html_resp.status_code == 200

        script_tags = re.findall(r'src="([^"]*health-guide/page[^"]*\.js)"', html_resp.text)
        assert script_tags, "未找到health-guide页面的JS chunk引用"

        js_url = script_tags[0]
        if js_url.startswith("/"):
            js_url = f"https://newbb.bangbangvip.com{js_url}"

        js_resp = page_client.get(js_url)
        assert js_resp.status_code == 200, f"JS chunk加载失败: {js_resp.status_code}"

        body = js_resp.text
        validation_keywords = ["请输入姓名", "请选择性别", "请选择出生日期"]
        found_keywords = [kw for kw in validation_keywords if kw in body]

        assert len(found_keywords) > 0, (
            f"健康引导页JS bundle中未找到任何校验提示文本 {validation_keywords}，"
            "修复可能未部署"
        )
