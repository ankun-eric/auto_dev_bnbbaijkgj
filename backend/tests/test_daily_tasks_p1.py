"""Bug #7 / Bug #8 P1 修复单元测试。

- Bug #7：任务列表中 complete_profile 的 route/target_url 必须为 /health-profile
- Bug #8：任务列表中不应再返回 first_order（已下线，enabled=False）
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_daily_tasks_first_order_removed_and_complete_profile_route(
    client: AsyncClient, auth_headers
):
    resp = await client.get("/api/points/tasks", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    items = data["items"]
    keys = [t["key"] for t in items]

    assert "first_order" not in keys, "Bug #8：first_order 应已被过滤（enabled=False）"

    complete_profile = next((t for t in items if t["key"] == "complete_profile"), None)
    assert complete_profile is not None, "complete_profile 任务必须存在"
    assert complete_profile["route"] == "/health-profile", (
        f"Bug #7：complete_profile.route 必须为 /health-profile，实际 {complete_profile['route']}"
    )
    assert complete_profile.get("target_url") == "/health-profile", (
        "Bug #7：complete_profile.target_url 必须为 /health-profile"
    )
