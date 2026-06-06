"""[PRD-FAMILY-GUARDIAN-V1] 公众号推送·中转页（H5 alert-redirect）后端测试。

覆盖：
- /api/alert/click-tracking 正常更新
- /api/alert/click-tracking 幂等（已 clicked 不再变更）
- /api/alert/click-tracking 不存在的 logId → 404
- /api/alert/click-tracking sig 校验失败 → 403
- /api/alert/click-tracking sig 校验成功 → 200
- /api/alert/verify 校验签名失败 → 403
- /api/alert/verify 校验签名成功 → 200
- /api/alert/event 白名单事件 → 200
- /api/alert/event 非法事件 → 400
"""

from __future__ import annotations

import time
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.models import FamilyAlertLog
from app.utils.alert_sig import sign_alert_redirect


# 自增计数器：手动分配 id 以兼容 SQLite 对 BigInteger autoincrement 的限制
_NEXT_LOG_ID = {"v": 10000}


def _alloc_log_id() -> int:
    _NEXT_LOG_ID["v"] += 1
    return _NEXT_LOG_ID["v"]


@pytest_asyncio.fixture
async def alert_log():
    """构造一条 sent 状态的 family_alert_logs，返回其 id 与基础信息。

    使用 conftest.test_session 直接写入；显式分配 id 兼容 SQLite + BigInteger 主键
    （SQLite 仅对 INTEGER PRIMARY KEY 自动递增，对 BIGINT 不行）。
    """
    from tests.conftest import test_session

    new_id = _alloc_log_id()
    member_id = 101
    report_id = 303
    async with test_session() as session:
        log = FamilyAlertLog(
            id=new_id,
            member_id=member_id,
            guardian_user_id=202,
            report_id=report_id,
            severity="warning",
            abnormal_count=5,
            template_code="checkup_abnormal_wechat_mp",
            channel="wechat_mp",
            delivery_status="sent",
            pushed_at=datetime.now(),
        )
        session.add(log)
        await session.commit()
    return {"id": new_id, "member_id": member_id, "report_id": report_id}


@pytest.mark.asyncio
async def test_click_tracking_normal(client: AsyncClient, alert_log):
    """无 sig 时：仅 logId 必填，校验通过则更新为 clicked。"""
    resp = await client.post(
        "/api/alert/click-tracking",
        json={"logId": alert_log["id"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == "clicked"
    assert body["log_id"] == alert_log["id"]


@pytest.mark.asyncio
async def test_click_tracking_idempotent(client: AsyncClient, alert_log):
    """重复点击：第二次应返回 idempotent=True，不再覆盖 clicked_at。"""
    r1 = await client.post(
        "/api/alert/click-tracking",
        json={"logId": alert_log["id"]},
    )
    assert r1.status_code == 200
    r2 = await client.post(
        "/api/alert/click-tracking",
        json={"logId": alert_log["id"]},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "clicked"
    assert body.get("idempotent") is True


@pytest.mark.asyncio
async def test_click_tracking_not_found(client: AsyncClient):
    resp = await client.post(
        "/api/alert/click-tracking",
        json={"logId": 99999999},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_click_tracking_with_valid_sig(client: AsyncClient, alert_log):
    """带 sig 时：sig 正确 → 通过。"""
    t = int(time.time())
    sig = sign_alert_redirect(
        log_id=alert_log["id"],
        member_id=alert_log["member_id"],
        report_id=alert_log["report_id"],
        t=t,
    )
    resp = await client.post(
        "/api/alert/click-tracking",
        json={
            "logId": alert_log["id"],
            "memberId": alert_log["member_id"],
            "reportId": alert_log["report_id"],
            "t": t,
            "sig": sig,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "clicked"


@pytest.mark.asyncio
async def test_click_tracking_with_invalid_sig(client: AsyncClient, alert_log):
    t = int(time.time())
    resp = await client.post(
        "/api/alert/click-tracking",
        json={
            "logId": alert_log["id"],
            "memberId": alert_log["member_id"],
            "reportId": alert_log["report_id"],
            "t": t,
            "sig": "deadbeefdeadbeef",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_click_tracking_partial_sig_rejected(client: AsyncClient, alert_log):
    """只传 t 不传 sig（或反之）应 403。"""
    resp = await client.post(
        "/api/alert/click-tracking",
        json={
            "logId": alert_log["id"],
            "t": int(time.time()),
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_alert_verify_ok(client: AsyncClient, alert_log):
    t = int(time.time())
    sig = sign_alert_redirect(
        log_id=alert_log["id"],
        member_id=alert_log["member_id"],
        report_id=alert_log["report_id"],
        t=t,
    )
    resp = await client.post(
        "/api/alert/verify",
        json={
            "logId": alert_log["id"],
            "memberId": alert_log["member_id"],
            "reportId": alert_log["report_id"],
            "t": t,
            "sig": sig,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_alert_verify_fail(client: AsyncClient, alert_log):
    resp = await client.post(
        "/api/alert/verify",
        json={
            "logId": alert_log["id"],
            "memberId": alert_log["member_id"],
            "reportId": alert_log["report_id"],
            "t": int(time.time()),
            "sig": "0" * 16,
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_alert_event_allowed(client: AsyncClient, alert_log):
    for evt in [
        "alert_redirect_view",
        "alert_redirect_app_launched",
        "alert_redirect_fallback_wechat",
        "alert_redirect_fallback_browser",
        "alert_redirect_click_weapp",
        "alert_redirect_click_download",
        "alert_redirect_click_h5",
    ]:
        resp = await client.post(
            "/api/alert/event",
            json={"event": evt, "logId": alert_log["id"]},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["event"] == evt


@pytest.mark.asyncio
async def test_alert_event_unknown_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/alert/event",
        json={"event": "alert_redirect_unknown_event"},
    )
    assert resp.status_code == 400
