"""
家庭共管优化 — 非UI自动化测试

覆盖：消息API、扫码路由、管理端消息、邀请二维码、接受/拒绝邀请的系统消息。
针对已部署的服务器执行，使用 requests 同步 HTTP 调用。

Run: pytest tests/test_family_comanage_optimize.py -v
"""

import random
import string
import uuid
import warnings

import pytest
import requests

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

BASE_URL = (
    "https://newbb.test.bangbangvip.com"
    "/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
)
API_URL = f"{BASE_URL}/api"

TEST_PHONE = "13800000001"
TEST_CODE = "123456"
ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"
TIMEOUT = 15


def _random_phone() -> str:
    return "138" + "".join(random.choices(string.digits, k=8))


# ─── fixtures ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.verify = False
    return s


@pytest.fixture(scope="module")
def user_token(session):
    """普通用户 SMS 验证码登录"""
    session.post(
        f"{API_URL}/auth/sms-code",
        json={"phone": TEST_PHONE, "type": "login"},
        timeout=TIMEOUT,
    )
    r = session.post(
        f"{API_URL}/auth/sms-login",
        json={"phone": TEST_PHONE, "code": TEST_CODE},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"用户登录失败: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="module")
def admin_token(session):
    """管理员密码登录"""
    r = session.post(
        f"{API_URL}/admin/login",
        json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"管理员登录失败: {r.status_code} {r.text}"
    data = r.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _register_and_login(session, phone=None):
    """注册并登录一个新用户，返回 (token, phone)"""
    phone = phone or _random_phone()
    nickname = f"test_{phone[-4:]}"
    session.post(
        f"{API_URL}/auth/register",
        json={"phone": phone, "password": "Test123456", "nickname": nickname},
        timeout=TIMEOUT,
    )
    r = session.post(
        f"{API_URL}/auth/login",
        json={"phone": phone, "password": "Test123456"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"登录失败({phone}): {r.status_code} {r.text}"
    return r.json()["access_token"], phone


def _create_family_member(session, token):
    """为用户创建一个家庭成员，返回 member_id"""
    headers = {"Authorization": f"Bearer {token}"}
    r = session.post(
        f"{API_URL}/family/members",
        headers=headers,
        json={
            "nickname": f"测试家人_{random.randint(1000, 9999)}",
            "relationship_type": "父亲",
            "gender": "male",
        },
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"创建家庭成员失败: {r.status_code} {r.text}"
    return r.json()["id"]


# ═══════════════════════════════════════════════════════════════
# 1-4: 消息 API（用户端）
# ═══════════════════════════════════════════════════════════════


class TestMessagesAPI:

    def test_messages_api_unread_count(self, session, user_headers):
        """test_messages_api_unread_count: 获取未读消息数量"""
        r = session.get(
            f"{API_URL}/messages/unread-count",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, (
            f"获取未读数失败: {r.status_code} {r.text}\n"
            f"请求: GET /api/messages/unread-count\n"
            f"预期: 200 + unread_count 字段"
        )
        data = r.json()
        assert "unread_count" in data, f"响应缺少 unread_count 字段: {data}"
        assert isinstance(data["unread_count"], int), "unread_count 应为整数"
        assert data["unread_count"] >= 0, "unread_count 不能为负数"

    def test_messages_api_list(self, session, user_headers):
        """test_messages_api_list: 消息列表接口（分页）"""
        r = session.get(
            f"{API_URL}/messages",
            headers=user_headers,
            params={"page": 1, "page_size": 10},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, (
            f"获取消息列表失败: {r.status_code} {r.text}\n"
            f"请求: GET /api/messages?page=1&page_size=10"
        )
        data = r.json()
        assert "items" in data, f"响应缺少 items 字段: {data}"
        assert "total" in data, f"响应缺少 total 字段: {data}"
        assert "page" in data, f"响应缺少 page 字段: {data}"
        assert "page_size" in data, f"响应缺少 page_size 字段: {data}"
        assert isinstance(data["items"], list)
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_messages_api_mark_read(self, session, user_headers):
        """test_messages_api_mark_read: 标记单条消息已读"""
        list_r = session.get(
            f"{API_URL}/messages",
            headers=user_headers,
            params={"page": 1, "page_size": 100},
            timeout=TIMEOUT,
        )
        assert list_r.status_code == 200
        items = list_r.json().get("items", [])

        if not items:
            pytest.skip("当前用户没有消息，跳过标记已读测试")

        msg_id = items[0]["id"]
        r = session.put(
            f"{API_URL}/messages/{msg_id}/read",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, (
            f"标记消息已读失败: {r.status_code} {r.text}\n"
            f"请求: PUT /api/messages/{msg_id}/read\n"
            f"预期: 200"
        )
        body = r.json()
        assert "message" in body or "已标记" in str(body), f"响应异常: {body}"

    def test_messages_api_mark_all_read(self, session, user_headers):
        """test_messages_api_mark_all_read: 标记所有消息已读"""
        r = session.put(
            f"{API_URL}/messages/read-all",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, (
            f"全部标记已读失败: {r.status_code} {r.text}\n"
            f"请求: PUT /api/messages/read-all"
        )

        count_r = session.get(
            f"{API_URL}/messages/unread-count",
            headers=user_headers,
            timeout=TIMEOUT,
        )
        assert count_r.status_code == 200
        assert count_r.json()["unread_count"] == 0, "全部已读后未读数应为 0"


# ═══════════════════════════════════════════════════════════════
# 5-6: 扫码路由
# ═══════════════════════════════════════════════════════════════


class TestScanAPI:

    def test_scan_api_family_invite(self, session, user_headers):
        """test_scan_api_family_invite: 扫码路由 type=family_invite（有效邀请码）"""
        token_a, _ = _register_and_login(session)
        member_id = _create_family_member(session, token_a)
        headers_a = {"Authorization": f"Bearer {token_a}"}

        inv_r = session.post(
            f"{API_URL}/family/invitation",
            headers=headers_a,
            json={"member_id": member_id},
            timeout=TIMEOUT,
        )
        assert inv_r.status_code == 200, f"创建邀请失败: {inv_r.status_code} {inv_r.text}"
        invite_code = inv_r.json()["invite_code"]

        r = session.get(
            f"{API_URL}/scan",
            params={"type": "family_invite", "code": invite_code},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, (
            f"扫码路由失败: {r.status_code} {r.text}\n"
            f"请求: GET /api/scan?type=family_invite&code={invite_code}"
        )
        data = r.json()
        assert data.get("type") == "family_invite", f"type 不匹配: {data}"
        assert "redirect_url" in data, f"缺少 redirect_url: {data}"
        assert "invitation" in data, f"缺少 invitation: {data}"
        assert data["invitation"]["invite_code"] == invite_code
        assert data["invitation"]["status"] == "pending"

    def test_scan_api_unknown_type(self, session):
        """test_scan_api_unknown_type: 扫码路由未知类型返回 400"""
        r = session.get(
            f"{API_URL}/scan",
            params={"type": "unknown_type_xyz", "code": "any_code"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400, (
            f"未知扫码类型应返回 400: 实际 {r.status_code} {r.text}\n"
            f"请求: GET /api/scan?type=unknown_type_xyz&code=any_code"
        )


# ═══════════════════════════════════════════════════════════════
# 7-9: 管理端消息 API
# ═══════════════════════════════════════════════════════════════


class TestAdminMessagesAPI:

    def test_admin_messages_list(self, session, admin_headers):
        """test_admin_messages_list: 管理端消息列表"""
        r = session.get(
            f"{API_URL}/admin/messages",
            headers=admin_headers,
            params={"page": 1, "page_size": 10},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, (
            f"管理端消息列表失败: {r.status_code} {r.text}\n"
            f"请求: GET /api/admin/messages?page=1&page_size=10"
        )
        data = r.json()
        assert "items" in data, f"响应缺少 items: {data}"
        assert "total" in data, f"响应缺少 total: {data}"
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    def test_admin_messages_stats(self, session, admin_headers):
        """test_admin_messages_stats: 管理端消息统计"""
        r = session.get(
            f"{API_URL}/admin/messages/stats",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, (
            f"管理端消息统计失败: {r.status_code} {r.text}\n"
            f"请求: GET /api/admin/messages/stats"
        )
        data = r.json()
        assert "total" in data, f"缺少 total: {data}"
        assert "unread" in data, f"缺少 unread: {data}"
        assert "type_counts" in data, f"缺少 type_counts: {data}"
        assert isinstance(data["total"], int)
        assert isinstance(data["unread"], int)
        assert isinstance(data["type_counts"], dict)
        assert data["total"] >= 0
        assert data["unread"] >= 0

    def test_admin_messages_send(self, session, admin_headers, user_token):
        """test_admin_messages_send: 管理端手动发送消息"""
        me_r = session.get(
            f"{API_URL}/auth/me",
            headers={"Authorization": f"Bearer {user_token}"},
            timeout=TIMEOUT,
        )
        if me_r.status_code != 200:
            pytest.skip("无法获取当前用户信息")
        recipient_id = me_r.json().get("id")
        if not recipient_id:
            pytest.skip("用户信息中无 id 字段")

        unique_title = f"自动化测试消息_{uuid.uuid4().hex[:8]}"
        r = session.post(
            f"{API_URL}/admin/messages",
            headers=admin_headers,
            json={
                "recipient_user_ids": [recipient_id],
                "message_type": "system",
                "title": unique_title,
                "content": "这是一条自动化测试消息",
            },
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, (
            f"管理端发送消息失败: {r.status_code} {r.text}\n"
            f"请求: POST /api/admin/messages\n"
            f"body: recipient_user_ids=[{recipient_id}], title={unique_title}"
        )
        data = r.json()
        assert "created_ids" in data, f"响应缺少 created_ids: {data}"
        assert len(data["created_ids"]) == 1, f"应创建 1 条消息: {data}"

        list_r = session.get(
            f"{API_URL}/messages",
            headers={"Authorization": f"Bearer {user_token}"},
            params={"page": 1, "page_size": 5},
            timeout=TIMEOUT,
        )
        if list_r.status_code == 200:
            titles = [m["title"] for m in list_r.json().get("items", [])]
            assert unique_title in titles, (
                f"发送的消息未出现在用户消息列表中\n"
                f"期望标题: {unique_title}\n"
                f"实际标题列表: {titles}"
            )


# ═══════════════════════════════════════════════════════════════
# 10: 邀请接口返回 qr_content_url
# ═══════════════════════════════════════════════════════════════


class TestInvitationQRContent:

    def test_invitation_qr_content_url(self, session):
        """test_invitation_qr_content_url: 创建邀请后返回 qr_content_url"""
        token_a, _ = _register_and_login(session)
        member_id = _create_family_member(session, token_a)
        headers_a = {"Authorization": f"Bearer {token_a}"}

        r = session.post(
            f"{API_URL}/family/invitation",
            headers=headers_a,
            json={"member_id": member_id},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"创建邀请失败: {r.status_code} {r.text}"
        data = r.json()

        assert "qr_content_url" in data, (
            f"响应缺少 qr_content_url 字段\n"
            f"实际响应: {data}"
        )
        qr_url = data["qr_content_url"]
        assert "scan" in qr_url, f"qr_content_url 应包含 scan 路径: {qr_url}"
        assert "family_invite" in qr_url, f"qr_content_url 应包含 family_invite: {qr_url}"
        assert data["invite_code"] in qr_url, (
            f"qr_content_url 应包含 invite_code: {qr_url}"
        )

        assert "invite_code" in data
        assert "expires_at" in data


# ═══════════════════════════════════════════════════════════════
# 11-12: 接受/拒绝邀请后双方系统消息
# ═══════════════════════════════════════════════════════════════


class TestInvitationMessages:

    @staticmethod
    def _setup_invitation(session):
        """创建两个用户、一个家庭成员、一条邀请，返回所需上下文"""
        token_a, phone_a = _register_and_login(session)
        token_b, phone_b = _register_and_login(session)
        member_id = _create_family_member(session, token_a)
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        inv_r = session.post(
            f"{API_URL}/family/invitation",
            headers=headers_a,
            json={"member_id": member_id},
            timeout=TIMEOUT,
        )
        assert inv_r.status_code == 200, f"创建邀请失败: {inv_r.status_code} {inv_r.text}"
        invite_code = inv_r.json()["invite_code"]

        return {
            "token_a": token_a,
            "token_b": token_b,
            "headers_a": headers_a,
            "headers_b": headers_b,
            "member_id": member_id,
            "invite_code": invite_code,
        }

    @staticmethod
    def _get_recent_messages(session, headers, page_size=20):
        r = session.get(
            f"{API_URL}/messages",
            headers=headers,
            params={"page": 1, "page_size": page_size},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            return []
        return r.json().get("items", [])

    def test_accept_invitation_sends_messages(self, session):
        """test_accept_invitation_sends_messages: 接受邀请后双方收到系统消息"""
        ctx = self._setup_invitation(session)

        r = session.post(
            f"{API_URL}/family/invitation/{ctx['invite_code']}/accept",
            headers=ctx["headers_b"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, (
            f"接受邀请失败: {r.status_code} {r.text}\n"
            f"请求: POST /api/family/invitation/{ctx['invite_code']}/accept"
        )

        msgs_a = self._get_recent_messages(session, ctx["headers_a"])
        accept_msgs_a = [
            m for m in msgs_a if m.get("message_type") == "family_invite_accepted"
        ]
        assert len(accept_msgs_a) >= 1, (
            f"邀请方应收到 family_invite_accepted 消息\n"
            f"邀请方消息列表类型: {[m.get('message_type') for m in msgs_a]}"
        )
        msg_a = accept_msgs_a[0]
        assert "共管" in msg_a.get("title", "") or "同意" in msg_a.get("title", ""), (
            f"邀请方消息标题异常: {msg_a.get('title')}"
        )

        msgs_b = self._get_recent_messages(session, ctx["headers_b"])
        accept_msgs_b = [
            m for m in msgs_b if m.get("message_type") == "family_invite_accepted"
        ]
        assert len(accept_msgs_b) >= 1, (
            f"被邀请方应收到 family_invite_accepted 消息\n"
            f"被邀请方消息列表类型: {[m.get('message_type') for m in msgs_b]}"
        )
        msg_b = accept_msgs_b[0]
        assert msg_b.get("related_business_type") == "family_management", (
            f"related_business_type 应为 family_management: {msg_b.get('related_business_type')}"
        )

    def test_reject_invitation_sends_messages(self, session):
        """test_reject_invitation_sends_messages: 拒绝邀请后双方收到系统消息"""
        ctx = self._setup_invitation(session)

        r = session.post(
            f"{API_URL}/family/invitation/{ctx['invite_code']}/reject",
            headers=ctx["headers_b"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, (
            f"拒绝邀请失败: {r.status_code} {r.text}\n"
            f"请求: POST /api/family/invitation/{ctx['invite_code']}/reject"
        )

        msgs_a = self._get_recent_messages(session, ctx["headers_a"])
        reject_msgs_a = [
            m for m in msgs_a if m.get("message_type") == "family_invite_rejected"
        ]
        assert len(reject_msgs_a) >= 1, (
            f"邀请方应收到 family_invite_rejected 消息\n"
            f"邀请方消息列表类型: {[m.get('message_type') for m in msgs_a]}"
        )
        msg_a = reject_msgs_a[0]
        assert "拒绝" in msg_a.get("title", ""), (
            f"邀请方消息标题应含'拒绝': {msg_a.get('title')}"
        )

        msgs_b = self._get_recent_messages(session, ctx["headers_b"])
        reject_msgs_b = [
            m for m in msgs_b if m.get("message_type") == "family_invite_rejected"
        ]
        assert len(reject_msgs_b) >= 1, (
            f"被邀请方应收到 family_invite_rejected 消息\n"
            f"被邀请方消息列表类型: {[m.get('message_type') for m in msgs_b]}"
        )
        msg_b = reject_msgs_b[0]
        assert msg_b.get("related_business_type") == "family_invitation", (
            f"related_business_type 应为 family_invitation: {msg_b.get('related_business_type')}"
        )
        click_params = msg_b.get("click_action_params")
        if click_params:
            assert click_params == "/family-bindlist" or isinstance(click_params, dict), (
                f"click_action_params 格式异常: {click_params}"
            )
