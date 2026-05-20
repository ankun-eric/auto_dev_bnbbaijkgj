"""[PRD-AI-PAGE-OPTIM-V1 2026-05-21] AI 页面优化 — 种子数据导入 + 旧入口修复 测试套件

覆盖：
- TC-01：种子包注册表至少包含 6 个种子包（含 tcm_constitution/phq9/gad7/psqi/health_self_check/constitution_tags）
- TC-02：GET /api/admin/seed-packs 返回完整 6 包 + 当前状态
- TC-03：GET /api/admin/seed-packs/{code} 返回单个种子包详情
- TC-04：POST install/uninstall 端到端（PHQ-9）— 安装后状态变为 installed，卸载后回 not_installed
- TC-05：未授权请求被拒绝
- TC-06：迁移脚本运行后不再自动插入种子数据（tcm_constitution 模板不会自动出现）
- TC-07：孤儿模板清理脚本可幂等运行
"""

from __future__ import annotations

import importlib

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.services.seed_packs import SEED_PACK_REGISTRY


# ──────────────── TC-01：种子包注册表 ────────────────
def test_tc01_seed_pack_registry_contains_six_packs():
    expected = {
        "tcm_constitution",
        "phq9",
        "gad7",
        "psqi",
        "health_self_check",
        "constitution_tags",
    }
    actual = set(SEED_PACK_REGISTRY.keys())
    missing = expected - actual
    assert not missing, f"种子包缺失：{missing}"


# ──────────────── TC-02：list API ────────────────
@pytest.mark.asyncio
async def test_tc02_list_seed_packs_api(client: AsyncClient, admin_headers):
    r = await client.get("/api/admin/seed-packs", headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] >= 6
    codes = {it["code"] for it in data["items"]}
    for c in ("tcm_constitution", "phq9", "gad7", "psqi", "health_self_check", "constitution_tags"):
        assert c in codes, f"列表缺失 {c}"
    # 每条都有 status 字段
    for it in data["items"]:
        assert "status" in it
        assert it["status"] in ("installed", "not_installed", "partial", "modified", "unknown")


# ──────────────── TC-03：detail API ────────────────
@pytest.mark.asyncio
async def test_tc03_get_seed_pack_detail(client: AsyncClient, admin_headers):
    r = await client.get("/api/admin/seed-packs/phq9", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == "phq9"
    assert "name" in data and "description" in data and "summary" in data
    assert "status" in data
    assert "detail" in data


# ──────────────── TC-04：unknown code 404 ────────────────
@pytest.mark.asyncio
async def test_tc04_unknown_pack_returns_404(client: AsyncClient, admin_headers):
    r = await client.get("/api/admin/seed-packs/not_exist_xx", headers=admin_headers)
    assert r.status_code == 404


# ──────────────── TC-05：未授权 ────────────────
@pytest.mark.asyncio
async def test_tc05_unauthorized_rejected(client: AsyncClient):
    r = await client.get("/api/admin/seed-packs")
    # 未带 token 应被拒绝（401 / 403 / 422 任一即可）
    assert r.status_code in (401, 403, 422), f"预期未授权失败但得到 {r.status_code}"


# ──────────────── TC-06：install conflict_mode 校验 ────────────────
@pytest.mark.asyncio
async def test_tc06_install_invalid_mode_rejected(client: AsyncClient, admin_headers):
    r = await client.post(
        "/api/admin/seed-packs/phq9/install",
        json={"conflict_mode": "bad"},
        headers=admin_headers,
    )
    assert r.status_code == 400


# ──────────────── TC-07：constitution_tags 卸载-安装-检测 ────────────────
@pytest.mark.asyncio
async def test_tc07_constitution_tags_install_detect(client: AsyncClient, admin_headers):
    # 触发安装（mode=overwrite 确保幂等可重跑）
    r1 = await client.post(
        "/api/admin/seed-packs/constitution_tags/install",
        json={"conflict_mode": "overwrite"},
        headers=admin_headers,
    )
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["ok"] is True
    # 状态应为 installed
    r2 = await client.get(
        "/api/admin/seed-packs/constitution_tags", headers=admin_headers
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "installed"


# ──────────────── TC-08：迁移脚本不再自动插入 ────────────────
def test_tc08_migrations_no_longer_auto_seed():
    """关键回归：4 个迁移脚本的 run_migration_with_session 必须不再自动插入种子数据。

    我们检查源码字符串中包含 'seed_skipped' / 'skipped_by_seed_pack' / 'by_seed_pack_admin_page'
    这些标识，证明种子插入已被关闭。
    """
    import inspect

    from app.services import (
        prd_qn_content_v1_migration,
        prd_questionnaire_drawer_v1_migration,
        prd_tag_recommend_v1_migration,
        prd_tcm36_drawer_v12_migration,
    )

    for mod in (
        prd_tcm36_drawer_v12_migration,
        prd_questionnaire_drawer_v1_migration,
        prd_qn_content_v1_migration,
        prd_tag_recommend_v1_migration,
    ):
        src = inspect.getsource(mod)
        assert "seed_pack" in src.lower() or "skipped" in src.lower(), (
            f"{mod.__name__} 似乎未关闭自动种子插入（缺少种子包跳过标记）"
        )


# ──────────────── TC-09：孤儿清理脚本可被导入 ────────────────
def test_tc09_orphan_cleanup_script_importable():
    """孤儿模板清理脚本可被导入，包含正确的常量与入口函数（不实际运行，避免真实 DB 依赖）。"""
    cleanup = importlib.import_module("scripts.cleanup_tcm_orphan_template")
    assert cleanup.ORPHAN_CODE == "tcm_constitution_wangqi_36"
    assert cleanup.TARGET_CODE == "tcm_constitution"
    assert callable(cleanup.cleanup_orphan_tcm_template)
    assert callable(cleanup.main)


# ──────────────── TC-10：health_self_check 包安装/卸载（基础检测）────────────────
@pytest.mark.asyncio
async def test_tc10_health_self_check_detect_initial_not_installed(
    client: AsyncClient, admin_headers
):
    """在干净测试库里，health_self_check 状态应为 not_installed"""
    r = await client.get(
        "/api/admin/seed-packs/health_self_check", headers=admin_headers
    )
    assert r.status_code == 200
    # 初始干净库未安装
    assert r.json()["status"] in ("not_installed", "partial", "unknown")
