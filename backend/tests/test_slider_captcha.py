"""滑块拼图验证码服务单元测试

Bug 修复 V1.0 / 2026-04-25：覆盖以下场景：
- 抽取挑战返回正确字段
- 位置正确 + 合理轨迹 → 通过并下发 token
- token 一次性（second take 失败）
- 位置错误 → 失败 + 计数
- 轨迹瞬移 / 直线 → trail_invalid
- 同 IP 连续 3 次失败 → 锁定 60 秒
- 锁定期间 verify 直接返回 locked
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import slider_captcha_service as svc


def _good_trail(target_x: int) -> list[dict]:
    """生成一条合理的轨迹：从 0 到 target_x，约 1 秒，带 y 抖动 + 速度变化"""
    points = []
    n = 20
    for i in range(n):
        ratio = i / (n - 1)
        # easing-like：先快后慢
        x = target_x * (1 - (1 - ratio) ** 2)
        y = (i % 3) - 1  # 在 -1/0/1 之间抖动
        t = 50 + 50 * i + (i * i) * 2  # 非匀速
        points.append({"x": x, "y": y, "t": t})
    return points


@pytest.fixture(autouse=True)
def _reset_store():
    svc._reset_store_for_test()
    yield
    svc._reset_store_for_test()


def test_issue_challenge_returns_required_fields():
    data = svc.issue_challenge()
    assert "challenge_id" in data and isinstance(data["challenge_id"], str)
    assert data["bg_image_base64"].startswith("data:image/")
    assert data["puzzle_image_base64"].startswith("data:image/")
    assert data["bg_width"] == svc.BG_WIDTH
    assert data["bg_height"] == svc.BG_HEIGHT
    assert data["puzzle_size"] == svc.PUZZLE_SIZE


def test_verify_success_returns_token():
    challenge = svc.issue_challenge()
    cid = challenge["challenge_id"]
    entry = svc._store._challenges[cid]
    target_x = entry.gap_x
    result = svc.verify(cid, target_x, _good_trail(target_x), client_ip="1.1.1.1")
    assert result["ok"] is True
    assert "captcha_token" in result and len(result["captcha_token"]) > 10
    assert result["expires_in"] == svc.TOKEN_TTL


def test_token_is_one_shot():
    challenge = svc.issue_challenge()
    cid = challenge["challenge_id"]
    target_x = svc._store._challenges[cid].gap_x
    result = svc.verify(cid, target_x, _good_trail(target_x), client_ip="1.1.1.1")
    token = result["captcha_token"]
    assert svc.take_token(token) is True
    # 二次取出应失败
    assert svc.take_token(token) is False


def test_position_mismatch_fails():
    challenge = svc.issue_challenge()
    cid = challenge["challenge_id"]
    target_x = svc._store._challenges[cid].gap_x
    wrong_x = target_x + 30
    result = svc.verify(cid, wrong_x, _good_trail(wrong_x), client_ip="2.2.2.2")
    assert result["ok"] is False
    assert result["reason"] == "position_mismatch"


def test_trail_too_few_points_fails():
    challenge = svc.issue_challenge()
    cid = challenge["challenge_id"]
    target_x = svc._store._challenges[cid].gap_x
    bad_trail = [{"x": 0, "y": 0, "t": 0}, {"x": target_x, "y": 1, "t": 100}]
    result = svc.verify(cid, target_x, bad_trail, client_ip="3.3.3.3")
    assert result["ok"] is False
    assert result["reason"] == "trail_invalid"


def test_trail_pure_horizontal_fails():
    """y 完全没抖动，全水平 → 视为脚本"""
    challenge = svc.issue_challenge()
    cid = challenge["challenge_id"]
    target_x = svc._store._challenges[cid].gap_x
    bad_trail = [{"x": (target_x * i / 9), "y": 0, "t": 100 + 80 * i} for i in range(10)]
    result = svc.verify(cid, target_x, bad_trail, client_ip="4.4.4.4")
    assert result["ok"] is False
    assert result["reason"] == "trail_invalid"


def test_consecutive_failures_lock_ip():
    ip = "9.9.9.9"
    for _ in range(svc.LOCK_FAIL_THRESHOLD):
        challenge = svc.issue_challenge()
        cid = challenge["challenge_id"]
        target_x = svc._store._challenges[cid].gap_x
        # 故意位置错
        svc.verify(cid, target_x + 50, _good_trail(target_x + 50), client_ip=ip)
    # 现在应被锁
    challenge = svc.issue_challenge()
    cid = challenge["challenge_id"]
    target_x = svc._store._challenges[cid].gap_x
    result = svc.verify(cid, target_x, _good_trail(target_x), client_ip=ip)
    assert result["ok"] is False
    assert result["reason"] == "locked"
    assert result["locked_seconds"] > 0


def test_expired_challenge_returns_challenge_expired():
    """take_challenge 取出后再用应失败"""
    challenge = svc.issue_challenge()
    cid = challenge["challenge_id"]
    target_x = svc._store._challenges[cid].gap_x
    svc.verify(cid, target_x, _good_trail(target_x), client_ip="5.5.5.5")
    # 二次校验同一个 challenge → 已被 consume
    result = svc.verify(cid, target_x, _good_trail(target_x), client_ip="5.5.5.5")
    assert result["ok"] is False
    assert result["reason"] == "challenge_expired"


# ─────────────── HTTP 路由测试 ───────────────

@pytest.mark.asyncio
async def test_http_issue_and_verify_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.get("/api/captcha/slider/issue")
        assert r1.status_code == 200
        body = r1.json()
        assert "challenge_id" in body
        cid = body["challenge_id"]
        target_x = svc._store._challenges[cid].gap_x

        r2 = await ac.post(
            "/api/captcha/slider/verify",
            json={"challenge_id": cid, "x": target_x, "trail": _good_trail(target_x)},
        )
        assert r2.status_code == 200
        r2body = r2.json()
        assert r2body["ok"] is True
        token = r2body["captcha_token"]
        assert token


@pytest.mark.asyncio
async def test_http_verify_position_wrong():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.get("/api/captcha/slider/issue")
        cid = r1.json()["challenge_id"]
        target_x = svc._store._challenges[cid].gap_x
        r2 = await ac.post(
            "/api/captcha/slider/verify",
            json={"challenge_id": cid, "x": target_x + 40, "trail": _good_trail(target_x + 40)},
        )
        body = r2.json()
        assert body["ok"] is False
        assert body["reason"] == "position_mismatch"
