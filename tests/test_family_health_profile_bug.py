"""
测试家庭成员健康档案 Bug 修复:
  添加家庭成员后，健康档案数据应同步创建且非空。

针对已部署的服务器执行非UI自动化测试。
"""

import uuid
import warnings

import pytest
import requests

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = (
    "https://newbb.bangbangvip.com"
    "/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api"
)
TEST_PHONE = "13800000001"
TEST_CODE = "123456"


@pytest.fixture(scope="module")
def auth_token():
    """获取登录 token（SMS 验证码登录）"""
    s = requests.Session()
    s.verify = False

    r = s.post(f"{BASE_URL}/auth/sms-code", json={"phone": TEST_PHONE, "type": "login"})
    assert r.status_code == 200, f"发送验证码失败: {r.status_code} {r.text}"

    r = s.post(f"{BASE_URL}/auth/sms-login", json={"phone": TEST_PHONE, "code": TEST_CODE})
    assert r.status_code == 200, f"登录失败: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    return token


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def session(headers):
    s = requests.Session()
    s.verify = False
    s.headers.update(headers)
    return s


@pytest.fixture(scope="module")
def self_member_id(session):
    """获取当前用户的 '本人' 成员 ID"""
    r = session.get(f"{BASE_URL}/family/members")
    assert r.status_code == 200
    items = r.json().get("items", [])
    for m in items:
        if m.get("is_self"):
            return m["id"]
    pytest.skip("当前用户没有 '本人' 成员记录")


# ─── helpers ──────────────────────────────────────────────

def _unique_name():
    return f"测试成员_{uuid.uuid4().hex[:6]}"


def _create_member(session, **overrides):
    payload = {
        "relationship_type": "爸爸",
        "name": _unique_name(),
        "gender": "男",
        "birthday": "1975-06-15",
        "height": 175.0,
        "weight": 72.5,
        "medical_histories": ["高血压", "糖尿病"],
        "allergies": ["青霉素", "花粉"],
    }
    payload.update(overrides)
    r = session.post(f"{BASE_URL}/family/members", json=payload)
    return r


def _get_health_profile(session, member_id):
    return session.get(f"{BASE_URL}/health/profile/member/{member_id}")


def _delete_member(session, member_id):
    return session.delete(f"{BASE_URL}/family/members/{member_id}")


# ─── 辅助测试 ─────────────────────────────────────────────

class TestFamilyBasic:
    """辅助测试：基本 CRUD"""

    def test_add_member_basic(self, session):
        """test_add_member_basic: 基本添加成员流程正常"""
        r = _create_member(session)
        assert r.status_code == 200, (
            f"添加成员失败: {r.status_code} {r.text}\n"
            f"请求: POST /api/family/members\n"
            f"预期: 200 成功\n"
            f"实际: {r.status_code} {r.text}"
        )
        data = r.json()
        assert data.get("id"), "返回数据缺少 id"
        assert data.get("relationship_type") == "爸爸"
        assert data.get("gender") == "男"
        _delete_member(session, data["id"])

    def test_list_family_members(self, session):
        """test_list_family_members: 成员列表正确返回"""
        r = session.get(f"{BASE_URL}/family/members")
        assert r.status_code == 200, f"获取成员列表失败: {r.status_code} {r.text}"
        data = r.json()
        assert "items" in data, "返回数据缺少 items 字段"
        assert "total" in data, "返回数据缺少 total 字段"
        assert isinstance(data["items"], list)
        assert data["total"] >= 1, "至少应有一个 '本人' 成员"

    def test_update_member_health_profile(self, session, self_member_id):
        """test_update_member_health_profile: 编辑成员健康档案正常"""
        update_payload = {
            "name": "自动测试更新",
            "height": 170.0,
            "weight": 65.0,
            "blood_type": "B",
        }
        r = session.put(
            f"{BASE_URL}/health/profile/member/{self_member_id}",
            json=update_payload,
        )
        assert r.status_code == 200, f"更新健康档案失败: {r.status_code} {r.text}"
        profile = r.json()
        assert profile.get("name") == "自动测试更新"
        assert profile.get("height") == 170.0
        assert profile.get("weight") == 65.0
        assert profile.get("blood_type") == "B"

    def test_delete_member(self, session):
        """test_delete_member: 删除成员正常（需要先创建成员）"""
        r1 = _create_member(session)
        if r1.status_code != 200:
            pytest.fail(
                f"[前置条件] 无法创建成员来测试删除: {r1.status_code} {r1.text}\n"
                f"请求: POST /api/family/members\n"
                f"实际: {r1.status_code} {r1.text}"
            )
        member_id = r1.json()["id"]

        r2 = _delete_member(session, member_id)
        assert r2.status_code == 200, f"删除成员失败: {r2.status_code} {r2.text}"

        r3 = session.get(f"{BASE_URL}/family/members")
        ids = [m["id"] for m in r3.json().get("items", [])]
        assert member_id not in ids, "删除后成员仍在列表中"


# ─── 核心测试（Bug 验证）────────────────────────────────

class TestHealthProfileBugFix:
    """核心测试：验证 Bug 修复 — 添加成员后健康档案数据同步"""

    def test_add_member_creates_health_profile(self, session):
        """
        test_add_member_creates_health_profile:
        添加新家庭成员后，GET /api/health/profile/member/{member_id}
        返回的健康档案数据非空且与添加时填写的数据一致。
        """
        name = _unique_name()
        r1 = _create_member(
            session,
            name=name,
            gender="女",
            birthday="1990-03-20",
            height=165.0,
            weight=55.0,
            medical_histories=["过敏性鼻炎"],
            allergies=["海鲜"],
        )
        assert r1.status_code == 200, (
            f"添加成员失败 — POST /api/family/members 返回 {r1.status_code}\n"
            f"请求体: name={name}, gender=女, birthday=1990-03-20, "
            f"height=165.0, weight=55.0\n"
            f"预期: 200 成功返回成员信息\n"
            f"实际: {r1.status_code} {r1.text}"
        )
        member_id = r1.json()["id"]

        r2 = _get_health_profile(session, member_id)
        assert r2.status_code == 200, (
            f"获取健康档案失败: {r2.status_code} {r2.text}"
        )
        profile = r2.json()

        assert profile.get("family_member_id") == member_id
        assert profile.get("name"), "健康档案 name 为空"
        assert profile.get("gender"), "健康档案 gender 为空"
        assert profile.get("birthday"), "健康档案 birthday 为空"
        assert profile.get("height") is not None, "健康档案 height 为空"
        assert profile.get("weight") is not None, "健康档案 weight 为空"

        _delete_member(session, member_id)

    def test_health_profile_data_consistency(self, session):
        """
        test_health_profile_data_consistency:
        验证添加成员时填写的各字段在健康档案中正确同步。
        """
        name = _unique_name()
        member_data = {
            "name": name,
            "gender": "男",
            "birthday": "1985-11-08",
            "height": 178.0,
            "weight": 75.5,
            "medical_histories": ["高血压", "冠心病"],
            "allergies": ["青霉素", "磺胺类药物"],
        }
        r1 = _create_member(session, **member_data)
        assert r1.status_code == 200, (
            f"添加成员失败 — POST /api/family/members 返回 {r1.status_code}\n"
            f"请求体: {member_data}\n"
            f"预期: 200\n"
            f"实际: {r1.status_code} {r1.text}"
        )
        member_id = r1.json()["id"]

        r2 = _get_health_profile(session, member_id)
        assert r2.status_code == 200, f"获取健康档案失败: {r2.status_code} {r2.text}"
        profile = r2.json()

        assert profile.get("name") == name, (
            f"name 不一致: 期望 {name}, 实际 {profile.get('name')}"
        )
        assert profile.get("gender") == "男", (
            f"gender 不一致: 期望 '男', 实际 {profile.get('gender')}"
        )
        assert profile.get("birthday") == "1985-11-08", (
            f"birthday 不一致: 期望 '1985-11-08', 实际 {profile.get('birthday')}"
        )
        assert profile.get("height") == 178.0, (
            f"height 不一致: 期望 178.0, 实际 {profile.get('height')}"
        )
        assert profile.get("weight") == 75.5, (
            f"weight 不一致: 期望 75.5, 实际 {profile.get('weight')}"
        )
        assert profile.get("medical_histories") == ["高血压", "冠心病"], (
            f"medical_histories 不一致: 期望 ['高血压', '冠心病'], "
            f"实际 {profile.get('medical_histories')}"
        )
        assert profile.get("allergies") == ["青霉素", "磺胺类药物"], (
            f"allergies 不一致: 期望 ['青霉素', '磺胺类药物'], "
            f"实际 {profile.get('allergies')}"
        )

        _delete_member(session, member_id)

    def test_existing_member_without_profile_backfill(self, session, self_member_id):
        """
        test_existing_member_without_profile_backfill:
        验证 GET /api/health/profile/member/{member_id} 接口的回填逻辑。
        对已有的 '本人' 成员（无需创建新成员），验证健康档案可以正确返回。
        """
        r = _get_health_profile(session, self_member_id)
        assert r.status_code == 200, (
            f"获取健康档案失败: {r.status_code} {r.text}\n"
            f"请求: GET /api/health/profile/member/{self_member_id}\n"
            f"预期: 200 返回健康档案\n"
            f"实际: {r.status_code} {r.text}"
        )
        profile = r.json()
        assert profile.get("family_member_id") == self_member_id, (
            f"family_member_id 不匹配: 期望 {self_member_id}, "
            f"实际 {profile.get('family_member_id')}"
        )
        assert profile.get("id") is not None, "健康档案 id 为空"
        assert profile.get("user_id") is not None, "健康档案 user_id 为空"
