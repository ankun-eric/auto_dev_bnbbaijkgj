"""
Server-side integration tests for health profile optimization.
Runs against the live deployed environment via HTTPS.
Tests disease-preset CRUD (with superuser permission) and mixed-format health profile fields.
"""

import random
import string

import httpx
import pytest

BASE_URL = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API_URL = f"{BASE_URL}/api"

_PHONE_SUFFIX = "".join(random.choices(string.digits, k=8))
TEST_PHONE = f"139{_PHONE_SUFFIX}"
TEST_PASSWORD = "TestPass1234"

ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=API_URL, verify=False, timeout=30) as c:
        yield c


@pytest.fixture(scope="module")
def user_token(client: httpx.Client):
    resp = client.post("/auth/register", json={
        "phone": TEST_PHONE,
        "password": TEST_PASSWORD,
        "nickname": f"档案测试{_PHONE_SUFFIX}",
    })
    if resp.status_code == 400 and "已注册" in resp.text:
        resp = client.post("/auth/login", json={
            "phone": TEST_PHONE,
            "password": TEST_PASSWORD,
        })
    assert resp.status_code == 200, f"Auth failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(user_token: str):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="module")
def admin_login_data(client: httpx.Client):
    resp = client.post("/admin/login", json={
        "phone": ADMIN_PHONE,
        "password": ADMIN_PASSWORD,
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    return resp.json()


@pytest.fixture(scope="module")
def admin_token(admin_login_data: dict):
    return admin_login_data["token"]


@pytest.fixture(scope="module")
def admin_is_superuser(admin_login_data: dict):
    return admin_login_data.get("user", {}).get("is_superuser", False)


@pytest.fixture(scope="module")
def admin_headers(admin_token: str):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def superuser_headers(client: httpx.Client, admin_headers: dict, admin_is_superuser: bool):
    """Return headers for a superuser admin. If the default admin is already superuser, use it directly."""
    if admin_is_superuser:
        return admin_headers
    pytest.skip("默认管理员不是超级管理员，跳过需要超级管理员权限的测试")


@pytest.fixture(scope="module")
def non_superuser_headers(client: httpx.Client):
    """Return headers for a non-superuser admin. Creates one if needed."""
    suffix = "".join(random.choices(string.digits, k=8))
    phone = f"136{suffix}"
    password = "NonSuper123"

    resp = client.post("/admin/login", json={"phone": phone, "password": password})
    if resp.status_code == 200:
        data = resp.json()
        if not data.get("user", {}).get("is_superuser", False):
            return {"Authorization": f"Bearer {data['token']}"}

    pytest.skip("无法获取非超级管理员账户进行权限测试")


@pytest.fixture(scope="module")
def self_member_id(client: httpx.Client, auth_headers: dict):
    resp = client.get("/family/members", headers=auth_headers)
    assert resp.status_code == 200, f"Failed to get family members: {resp.text}"
    items = resp.json()["items"]
    for m in items:
        if m.get("is_self"):
            return m["id"]
    pytest.fail("No is_self=True member found in family members list")


# ── TC-001: 获取过敏预设标签 ──

class TestGetAllergyPresets:
    def test_get_allergy_presets(self, client: httpx.Client):
        resp = client.get("/disease-presets", params={"category": "allergy"})
        assert resp.status_code == 200, (
            f"获取过敏预设标签失败: status={resp.status_code}, body={resp.text}"
        )
        data = resp.json()
        assert "items" in data, f"响应缺少 items 字段: {data}"

        for item in data["items"]:
            assert "id" in item, f"预设缺少 id: {item}"
            assert "name" in item, f"预设缺少 name: {item}"
            assert "category" in item, f"预设缺少 category: {item}"
            assert item["category"] == "allergy", (
                f"预设 category 不是 allergy: {item}"
            )


# ── TC-002: 获取慢性病/遗传病预设标签 ──

class TestGetChronicAndGeneticPresets:
    def test_get_chronic_presets(self, client: httpx.Client):
        resp = client.get("/disease-presets", params={"category": "chronic"})
        assert resp.status_code == 200, (
            f"获取慢性病预设标签失败: status={resp.status_code}, body={resp.text}"
        )
        data = resp.json()
        assert "items" in data
        for item in data["items"]:
            assert item["category"] == "chronic", (
                f"预设 category 不是 chronic: {item}"
            )

    def test_get_genetic_presets(self, client: httpx.Client):
        resp = client.get("/disease-presets", params={"category": "genetic"})
        assert resp.status_code == 200, (
            f"获取遗传病预设标签失败: status={resp.status_code}, body={resp.text}"
        )
        data = resp.json()
        assert "items" in data
        for item in data["items"]:
            assert item["category"] == "genetic", (
                f"预设 category 不是 genetic: {item}"
            )


# ── TC-003: 超级管理员创建预设标签 ──

class TestSuperuserCreatePreset:
    def test_superuser_create_preset(self, client: httpx.Client, superuser_headers: dict):
        suffix = "".join(random.choices(string.ascii_lowercase, k=4))
        resp = client.post("/admin/disease-presets", json={
            "name": f"测试过敏原_{suffix}",
            "category": "allergy",
            "sort_order": 99,
            "is_active": True,
        }, headers=superuser_headers)
        assert resp.status_code == 200, (
            f"超级管理员创建预设失败: status={resp.status_code}, body={resp.text}"
        )
        data = resp.json()
        assert "id" in data, f"创建响应缺少 id: {data}"
        assert data["name"].startswith("测试过敏原_")
        assert data["category"] == "allergy"


# ── TC-004: 普通管理员创建预设标签被拒绝 ──

class TestNonSuperuserCreatePresetDenied:
    def test_non_superuser_create_preset_denied(
        self, client: httpx.Client, non_superuser_headers: dict
    ):
        resp = client.post("/admin/disease-presets", json={
            "name": "普通管理员测试",
            "category": "allergy",
        }, headers=non_superuser_headers)
        assert resp.status_code == 403, (
            f"期望 403, 实际: status={resp.status_code}, body={resp.text}"
        )


# ── TC-005: 超级管理员更新预设标签 ──

class TestSuperuserUpdatePreset:
    def test_superuser_update_preset(self, client: httpx.Client, superuser_headers: dict):
        create_resp = client.post("/admin/disease-presets", json={
            "name": "待更新预设",
            "category": "chronic",
            "sort_order": 0,
        }, headers=superuser_headers)
        assert create_resp.status_code == 200, (
            f"创建预设失败: {create_resp.text}"
        )
        preset_id = create_resp.json()["id"]

        update_resp = client.put(f"/admin/disease-presets/{preset_id}", json={
            "name": "已更新预设",
            "category": "genetic",
        }, headers=superuser_headers)
        assert update_resp.status_code == 200, (
            f"超级管理员更新预设失败: status={update_resp.status_code}, body={update_resp.text}"
        )
        data = update_resp.json()
        assert data["name"] == "已更新预设"
        assert data["category"] == "genetic"


# ── TC-006: 普通管理员更新预设标签被拒绝 ──

class TestNonSuperuserUpdatePresetDenied:
    def test_non_superuser_update_preset_denied(
        self, client: httpx.Client, superuser_headers: dict, non_superuser_headers: dict
    ):
        create_resp = client.post("/admin/disease-presets", json={
            "name": "权限测试预设",
            "category": "chronic",
        }, headers=superuser_headers)
        assert create_resp.status_code == 200
        preset_id = create_resp.json()["id"]

        resp = client.put(f"/admin/disease-presets/{preset_id}", json={
            "name": "不应成功",
        }, headers=non_superuser_headers)
        assert resp.status_code == 403, (
            f"期望 403, 实际: status={resp.status_code}, body={resp.text}"
        )


# ── TC-007: 超级管理员删除预设标签 ──

class TestSuperuserDeletePreset:
    def test_superuser_delete_preset(self, client: httpx.Client, superuser_headers: dict):
        create_resp = client.post("/admin/disease-presets", json={
            "name": "待删除预设",
            "category": "allergy",
        }, headers=superuser_headers)
        assert create_resp.status_code == 200
        preset_id = create_resp.json()["id"]

        del_resp = client.delete(
            f"/admin/disease-presets/{preset_id}",
            headers=superuser_headers,
        )
        assert del_resp.status_code == 200, (
            f"超级管理员删除预设失败: status={del_resp.status_code}, body={del_resp.text}"
        )


# ── TC-008: 普通管理员删除预设标签被拒绝 ──

class TestNonSuperuserDeletePresetDenied:
    def test_non_superuser_delete_preset_denied(
        self, client: httpx.Client, superuser_headers: dict, non_superuser_headers: dict
    ):
        create_resp = client.post("/admin/disease-presets", json={
            "name": "删除权限测试",
            "category": "genetic",
        }, headers=superuser_headers)
        assert create_resp.status_code == 200
        preset_id = create_resp.json()["id"]

        resp = client.delete(
            f"/admin/disease-presets/{preset_id}",
            headers=non_superuser_headers,
        )
        assert resp.status_code == 403, (
            f"期望 403, 实际: status={resp.status_code}, body={resp.text}"
        )


# ── TC-009: 健康档案保存混合格式慢性病史 ──

class TestMixedFormatChronicDiseases:
    def test_save_mixed_chronic_diseases(
        self, client: httpx.Client, auth_headers: dict
    ):
        mixed_data = ["高血压", {"type": "custom", "value": "罕见病XXX"}]
        resp = client.put("/health/profile", json={
            "chronic_diseases": mixed_data,
        }, headers=auth_headers)
        assert resp.status_code == 200, (
            f"保存混合格式慢性病史失败: status={resp.status_code}, body={resp.text}"
        )

        get_resp = client.get("/health/profile", headers=auth_headers)
        assert get_resp.status_code == 200, (
            f"获取健康档案失败: status={get_resp.status_code}, body={get_resp.text}"
        )
        profile = get_resp.json()
        chronic = profile.get("chronic_diseases")
        assert chronic is not None, "chronic_diseases 为空"
        assert len(chronic) == 2, f"期望 2 项, 实际 {len(chronic)}: {chronic}"

        has_string = any(isinstance(d, str) and d == "高血压" for d in chronic)
        has_custom = any(
            isinstance(d, dict) and d.get("type") == "custom" and d.get("value") == "罕见病XXX"
            for d in chronic
        )
        assert has_string, f"未找到字符串格式 '高血压': {chronic}"
        assert has_custom, f"未找到自定义格式 '罕见病XXX': {chronic}"


# ── TC-010: 健康档案保存混合格式过敏史 ──

class TestMixedFormatAllergies:
    def test_save_mixed_allergies(
        self, client: httpx.Client, auth_headers: dict
    ):
        mixed_data = ["青霉素", {"type": "custom", "value": "特殊过敏原"}]
        resp = client.put("/health/profile", json={
            "allergies": mixed_data,
        }, headers=auth_headers)
        assert resp.status_code == 200, (
            f"保存混合格式过敏史失败: status={resp.status_code}, body={resp.text}"
        )

        get_resp = client.get("/health/profile", headers=auth_headers)
        assert get_resp.status_code == 200
        profile = get_resp.json()
        allergies = profile.get("allergies")
        assert allergies is not None, "allergies 为空"
        assert len(allergies) == 2, f"期望 2 项, 实际 {len(allergies)}: {allergies}"


# ── TC-011: 健康档案保存混合格式遗传病史 ──

class TestMixedFormatGeneticDiseases:
    def test_save_mixed_genetic_diseases(
        self, client: httpx.Client, auth_headers: dict
    ):
        mixed_data = ["地中海贫血", {"type": "custom", "value": "罕见遗传病YYY"}]
        resp = client.put("/health/profile", json={
            "genetic_diseases": mixed_data,
        }, headers=auth_headers)
        assert resp.status_code == 200, (
            f"保存混合格式遗传病史失败: status={resp.status_code}, body={resp.text}"
        )

        get_resp = client.get("/health/profile", headers=auth_headers)
        assert get_resp.status_code == 200
        profile = get_resp.json()
        genetic = profile.get("genetic_diseases")
        assert genetic is not None, "genetic_diseases 为空"
        assert len(genetic) == 2, f"期望 2 项, 实际 {len(genetic)}: {genetic}"


# ── TC-012: 家庭成员健康档案保存混合格式 ──

class TestMemberProfileMixedFormat:
    def test_member_profile_mixed_format(
        self, client: httpx.Client, auth_headers: dict, self_member_id: int
    ):
        mixed_chronic = ["糖尿病", {"type": "custom", "value": "罕见慢性病"}]
        mixed_allergies = ["花粉", {"type": "custom", "value": "特殊过敏"}]
        mixed_genetic = ["色盲", {"type": "custom", "value": "遗传代谢病"}]

        resp = client.put(
            f"/health/profile/member/{self_member_id}",
            json={
                "chronic_diseases": mixed_chronic,
                "allergies": mixed_allergies,
                "genetic_diseases": mixed_genetic,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200, (
            f"家庭成员混合格式保存失败: status={resp.status_code}, body={resp.text}"
        )

        data = resp.json()
        assert data.get("chronic_diseases") is not None, "chronic_diseases 为空"
        assert len(data["chronic_diseases"]) == 2
        assert data.get("allergies") is not None, "allergies 为空"
        assert len(data["allergies"]) == 2
        assert data.get("genetic_diseases") is not None, "genetic_diseases 为空"
        assert len(data["genetic_diseases"]) == 2
