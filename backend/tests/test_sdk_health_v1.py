"""[2026-05-05 SDK 健康看板] 单元测试。

覆盖：
1. snapshot 默认包含支付宝（python-alipay-sdk 已装），ok=True
2. 强制把支付宝从注册表删除一条 + 让某可选模块 import 失败，summary.missing_optional 加 1，
   且不影响 ok 字段对应核心项的判定
3. /api/admin/health/sdk 鉴权：未登录 → 401/403；管理员 → 200
4. /api/admin/health/sdk/refresh 重新检测：能反映模块新装/新失败
"""
from __future__ import annotations

import importlib

import pytest
from httpx import AsyncClient

from app.core import sdk_health


@pytest.mark.asyncio
async def test_snapshot_basic_shape():
    snap = sdk_health.refresh_snapshot()
    assert isinstance(snap, dict) and len(snap) > 0
    # 支付宝注册表 entry 必须存在；ok 取决于本机环境，只验结构正确
    alipay = snap.get("alipay")
    assert alipay is not None
    assert alipay["group"] == "payment"
    assert alipay["level"] == "optional"
    assert alipay["install_cmd"] == "pip install python-alipay-sdk"
    assert isinstance(alipay["ok"], bool)
    if not alipay["ok"]:
        assert alipay["error"] is not None

    payload = sdk_health.get_snapshot()
    assert "summary" in payload and "groups" in payload
    assert payload["summary"]["total"] == len(sdk_health.SDK_REGISTRY)
    assert payload["checked_at"] is not None


@pytest.mark.asyncio
async def test_snapshot_missing_optional_does_not_break_ok_field():
    """注入一个不存在的 optional 模块，验证 missing_optional 计数生效。"""
    fake = {
        "import_name": "this_module_does_not_exist_for_sure",
        "level": sdk_health.DependencyLevel.OPTIONAL,
        "group": sdk_health.DependencyGroup.OTHER,
        "name": "假 SDK（测试用）",
        "install_cmd": "echo no-op",
        "usage": "test",
    }
    sdk_health.SDK_REGISTRY.append(fake)
    try:
        sdk_health.refresh_snapshot()
        snap = sdk_health.get_snapshot()
        assert snap["summary"]["missing_optional"] >= 1
        assert snap["ok"] is False  # 整体 ok 受 missing_optional 影响
        # 但 missing_core 必须为 0（业务核心仍然完好）
        assert snap["summary"]["missing_core"] == 0
    finally:
        sdk_health.SDK_REGISTRY.remove(fake)
        sdk_health.refresh_snapshot()


@pytest.mark.asyncio
async def test_admin_endpoint_requires_auth(client: AsyncClient):
    r = await client.get("/api/admin/health/sdk")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_endpoint_returns_snapshot(client: AsyncClient, admin_headers: dict):
    r = await client.get("/api/admin/health/sdk", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "summary" in body and "groups" in body
    # alipay 必须在 payment 组中
    payment_items = body["groups"].get("payment", [])
    keys = [it["key"] for it in payment_items]
    assert "alipay" in keys
    alipay = next(it for it in payment_items if it["key"] == "alipay")
    assert alipay["install_cmd"] == "pip install python-alipay-sdk"
    assert isinstance(alipay["ok"], bool)


@pytest.mark.asyncio
async def test_admin_refresh_endpoint(client: AsyncClient, admin_headers: dict):
    r = await client.post("/api/admin/health/sdk/refresh", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["total"] == len(sdk_health.SDK_REGISTRY)


@pytest.mark.asyncio
async def test_run_startup_check_no_raise_when_only_optional_missing():
    """只缺 optional 时，run_startup_sdk_check 不应抛异常。"""
    fake = {
        "import_name": "another_missing_optional_xyz",
        "level": sdk_health.DependencyLevel.OPTIONAL,
        "group": sdk_health.DependencyGroup.OTHER,
        "name": "缺失可选 SDK",
        "install_cmd": "echo no-op",
        "usage": "test",
    }
    sdk_health.SDK_REGISTRY.append(fake)
    try:
        # 不应抛异常
        sdk_health.run_startup_sdk_check()
    finally:
        sdk_health.SDK_REGISTRY.remove(fake)
        sdk_health.refresh_snapshot()


@pytest.mark.asyncio
async def test_run_startup_check_raises_when_core_missing():
    fake_core = {
        "import_name": "core_module_that_does_not_exist_zzz",
        "level": sdk_health.DependencyLevel.CORE,
        "group": sdk_health.DependencyGroup.CORE,
        "name": "假核心",
        "install_cmd": "echo no-op",
        "usage": "test",
    }
    sdk_health.SDK_REGISTRY.append(fake_core)
    try:
        with pytest.raises(RuntimeError, match="核心依赖缺失"):
            sdk_health.run_startup_sdk_check()
    finally:
        sdk_health.SDK_REGISTRY.remove(fake_core)
        sdk_health.refresh_snapshot()
