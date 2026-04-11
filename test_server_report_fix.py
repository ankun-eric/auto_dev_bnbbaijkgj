"""Server-side integration tests for the OCR report bug fix.

Target: https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857
"""

import io
import random
import time

import httpx
import pytest
from PIL import Image

BASE = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API = f"{BASE}/api"

ADMIN_PHONE = "13800000000"
ADMIN_PASSWORD = "admin123"

TEST_USER_PHONE = f"138{random.randint(10000000, 99999999)}"
TEST_USER_PASSWORD = "test123456"
TEST_USER_NICKNAME = "OCR测试用户"

TIMEOUT = 30.0


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_test_jpeg(width: int = 600, height: int = 400) -> bytes:
    """Generate a random-pixel JPEG >10 KB that passes quality checks."""
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    rng = random.Random(42)
    for x in range(width):
        for y in range(height):
            pixels[x, y] = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    data = buf.getvalue()
    assert len(data) > 10 * 1024, f"JPEG too small: {len(data)} bytes"
    return data


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── shared state across ordered tests ─────────────────────────────────────────

class _State:
    admin_token: str = ""
    user_token: str = ""
    uploaded_report_id: int = 0
    share_token: str = ""


state = _State()


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=API, timeout=TIMEOUT, verify=False) as c:
        yield c


# ── 1. health ─────────────────────────────────────────────────────────────────

def test_health(client: httpx.Client):
    r = client.get("/health")
    assert r.status_code == 200, f"health returned {r.status_code}: {r.text}"
    data = r.json()
    assert data.get("status") == "ok"


# ── 2. admin login ────────────────────────────────────────────────────────────

def test_admin_login(client: httpx.Client):
    r = client.post("/admin/login", json={"phone": ADMIN_PHONE, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed ({r.status_code}): {r.text}"
    data = r.json()
    assert "token" in data, f"no token in response: {data}"
    state.admin_token = data["token"]


# ── 3. user register + login ─────────────────────────────────────────────────

def test_user_register_and_login(client: httpx.Client):
    r = client.post("/auth/register", json={
        "phone": TEST_USER_PHONE,
        "password": TEST_USER_PASSWORD,
        "nickname": TEST_USER_NICKNAME,
    })
    if r.status_code == 200:
        data = r.json()
        token = data.get("access_token")
        assert token, f"no access_token in register response: {data}"
        state.user_token = token
        return

    r2 = client.post("/auth/login", json={
        "phone": TEST_USER_PHONE,
        "password": TEST_USER_PASSWORD,
    })
    assert r2.status_code == 200, (
        f"register({r.status_code}): {r.text}; login({r2.status_code}): {r2.text}"
    )
    data2 = r2.json()
    token = data2.get("access_token")
    assert token, f"no access_token in login response: {data2}"
    state.user_token = token


# ── 4. OCR config exists ─────────────────────────────────────────────────────

def test_ocr_config_exists(client: httpx.Client):
    assert state.admin_token, "admin token not set"
    r = client.get("/admin/ocr/config", headers=_auth_header(state.admin_token))
    assert r.status_code == 200, f"ocr config returned {r.status_code}: {r.text}"
    data = r.json()
    assert data.get("enabled") is True, f"OCR not enabled: {data}"


# ── 5. upload report image ───────────────────────────────────────────────────

def test_upload_report_image(client: httpx.Client):
    assert state.user_token, "user token not set"
    jpeg = _make_test_jpeg()
    r = client.post(
        "/report/upload",
        files={"file": ("test_report.jpg", jpeg, "image/jpeg")},
        headers=_auth_header(state.user_token),
    )
    assert r.status_code == 200, f"upload failed ({r.status_code}): {r.text}"
    data = r.json()
    assert data.get("status") == "pending", f"unexpected status: {data}"
    assert data.get("file_type") == "image", f"unexpected file_type: {data}"
    assert "id" in data, f"no id in upload response: {data}"
    state.uploaded_report_id = data["id"]


# ── 6. upload unsupported format ──────────────────────────────────────────────

def test_upload_report_unsupported_format(client: httpx.Client):
    assert state.user_token, "user token not set"
    r = client.post(
        "/report/upload",
        files={"file": ("test.txt", b"plain text content here", "text/plain")},
        headers=_auth_header(state.user_token),
    )
    assert r.status_code == 400, f"expected 400 for .txt, got {r.status_code}: {r.text}"


# ── 7. report list ───────────────────────────────────────────────────────────

def test_report_list(client: httpx.Client):
    assert state.user_token, "user token not set"
    r = client.get("/report/list", headers=_auth_header(state.user_token))
    assert r.status_code == 200, f"report list failed ({r.status_code}): {r.text}"
    data = r.json()
    assert "items" in data, f"missing 'items': {data}"
    assert "total" in data, f"missing 'total': {data}"
    assert "page" in data, f"missing 'page': {data}"
    assert isinstance(data["items"], list)


# ── 8. report detail ─────────────────────────────────────────────────────────

def test_report_detail(client: httpx.Client):
    assert state.user_token, "user token not set"
    assert state.uploaded_report_id, "no uploaded report id"
    r = client.get(
        f"/report/detail/{state.uploaded_report_id}",
        headers=_auth_header(state.user_token),
    )
    assert r.status_code == 200, f"detail failed ({r.status_code}): {r.text}"
    data = r.json()
    assert data.get("id") == state.uploaded_report_id


# ── 9. report detail not found ───────────────────────────────────────────────

def test_report_detail_not_found(client: httpx.Client):
    assert state.user_token, "user token not set"
    r = client.get("/report/detail/99999", headers=_auth_header(state.user_token))
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"


# ── 10. report list unauthorized ─────────────────────────────────────────────

def test_report_list_unauthorized(client: httpx.Client):
    r = client.get("/report/list")
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"


# ── 11. upload unauthorized ──────────────────────────────────────────────────

def test_upload_unauthorized(client: httpx.Client):
    r = client.post(
        "/report/upload",
        files={"file": ("t.jpg", b"\xff\xd8" + b"\x00" * 1024, "image/jpeg")},
    )
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"


# ── 12. alerts list ──────────────────────────────────────────────────────────

def test_alerts_list(client: httpx.Client):
    assert state.user_token, "user token not set"
    r = client.get("/report/alerts", headers=_auth_header(state.user_token))
    assert r.status_code == 200, f"alerts failed ({r.status_code}): {r.text}"
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert isinstance(data["items"], list)


# ── 13. trend data ───────────────────────────────────────────────────────────

def test_trend_data(client: httpx.Client):
    assert state.user_token, "user token not set"
    r = client.get("/report/trend/血红蛋白", headers=_auth_header(state.user_token))
    assert r.status_code == 200, f"trend failed ({r.status_code}): {r.text}"
    data = r.json()
    assert "indicator_name" in data, f"missing indicator_name: {data}"
    assert data["indicator_name"] == "血红蛋白"
    assert "data_points" in data, f"missing data_points: {data}"
    assert isinstance(data["data_points"], list)


# ── 14. share create ─────────────────────────────────────────────────────────

def test_share_create(client: httpx.Client):
    assert state.user_token, "user token not set"
    assert state.uploaded_report_id, "no uploaded report id"
    r = client.post(
        "/report/share",
        json={"report_id": state.uploaded_report_id},
        headers=_auth_header(state.user_token),
    )
    assert r.status_code == 200, f"share create failed ({r.status_code}): {r.text}"
    data = r.json()
    assert "share_token" in data, f"missing share_token: {data}"
    assert "share_url" in data, f"missing share_url: {data}"
    assert "expires_at" in data, f"missing expires_at: {data}"
    state.share_token = data["share_token"]


# ── 15. share view ───────────────────────────────────────────────────────────

def test_share_view(client: httpx.Client):
    assert state.share_token, "share token not set"
    r = client.get(f"/report/share/{state.share_token}")
    assert r.status_code == 200, f"share view failed ({r.status_code}): {r.text}"
    data = r.json()
    assert "abnormal_count" in data
    assert "disclaimer" in data


# ── 16. improved error message ────────────────────────────────────────────────

def test_improved_error_message(client: httpx.Client):
    """Verify the bug fix: analyze should NOT return the old vague
    '未能提取报告文字' message. It should either succeed or return
    a precise error like '报告文件不存在或已失效' / 'OCR未能识别到文字内容'."""
    assert state.user_token, "user token not set"
    assert state.uploaded_report_id, "no uploaded report id"

    r = client.post(
        "/report/analyze",
        json={"report_id": state.uploaded_report_id},
        headers=_auth_header(state.user_token),
    )

    if r.status_code == 200:
        data = r.json()
        assert data.get("status") in ("completed", "analyzing"), f"unexpected status: {data}"
        return

    detail = r.json().get("detail", "")
    old_vague_messages = ["未能提取报告文字", "文件不存在"]
    for old_msg in old_vague_messages:
        if old_msg in detail:
            assert "重新上传" in detail or "OCR" in detail, (
                f"Error message not improved — still uses vague wording: '{detail}'"
            )

    assert r.status_code in (400, 500, 503), (
        f"unexpected status {r.status_code} from analyze: {r.text}"
    )
