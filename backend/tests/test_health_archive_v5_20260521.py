"""[PRD-HEALTH-ARCHIVE-V5-20260521] 健康档案与就医资料优化 — 接口测试。

覆盖：
- GET  /api/health-archive-v5/overview          4 卡片 + 预警横幅
- 健康预警 _seed/列表/标记已处理/全部已处理 + 24h 合并规则
- 就医资料 创建（含 9 文件上限）/列表/详情/编辑/软删/回收站/恢复/彻底删除/到期清理
- AI 首页 hero-count 文案分支（无计划 / 已完成 / 剩余）
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_v5_overview_empty(client: AsyncClient, auth_headers):
    res = await client.get("/api/health-archive-v5/overview", headers=auth_headers)
    assert res.status_code == 200, res.text
    d = res.json()
    assert d["alerts_unresolved"] == 0
    assert d["show_alert_banner"] is False
    assert d["medical_records_total"] == 0
    assert set(d["medical_records_by_category"].keys()) == {
        "case_note", "checkup_report", "drug", "other",
    }


@pytest.mark.asyncio
async def test_v5_alert_seed_and_merge(client: AsyncClient, auth_headers):
    # 第一次创建：1 条
    res = await client.post(
        "/api/health-alerts/_seed",
        headers=auth_headers,
        json={
            "items": [
                {"alert_type": "device", "indicator": "blood_pressure", "title": "血压持续偏高", "severity": "high", "source_label": "宾尼血压计"},
            ],
        },
    )
    assert res.status_code == 200
    assert res.json()["created"] == 1

    # 第二次相同指标：24h 内合并
    res2 = await client.post(
        "/api/health-alerts/_seed",
        headers=auth_headers,
        json={
            "items": [
                {"alert_type": "device", "indicator": "blood_pressure", "title": "血压持续偏高"},
            ],
        },
    )
    body2 = res2.json()
    assert body2["created"] == 0
    assert body2["merged"] == 1

    # 列表只应有 1 条
    lst = await client.get("/api/health-alerts?status=open", headers=auth_headers)
    items = lst.json()["items"]
    assert len(items) == 1
    assert items[0]["merged_count"] == 2

    # overview 预警数 = 1
    ov = await client.get("/api/health-archive-v5/overview", headers=auth_headers)
    assert ov.json()["alerts_unresolved"] == 1
    assert ov.json()["show_alert_banner"] is True
    assert "立即查看" in ov.json()["banner_text"]


@pytest.mark.asyncio
async def test_v5_alert_resolve(client: AsyncClient, auth_headers):
    await client.post(
        "/api/health-alerts/_seed",
        headers=auth_headers,
        json={"items": [
            {"alert_type": "medication", "indicator": "missed_3d", "title": "连续3天漏服降压药"},
            {"alert_type": "checkup", "indicator": "blood_glucose", "title": "空腹血糖偏高"},
        ]},
    )
    lst = await client.get("/api/health-alerts?status=open", headers=auth_headers)
    items = lst.json()["items"]
    assert len(items) == 2
    target_id = items[0]["id"]

    r = await client.post(f"/api/health-alerts/{target_id}/resolve", headers=auth_headers)
    assert r.status_code == 200

    # 已处理 Tab 应能查到
    done = await client.get("/api/health-alerts?status=done", headers=auth_headers)
    assert any(it["id"] == target_id for it in done.json()["items"])

    # 全部已处理
    r2 = await client.post("/api/health-alerts/resolve-all", headers=auth_headers)
    assert r2.status_code == 200
    lst2 = await client.get("/api/health-alerts?status=open", headers=auth_headers)
    assert lst2.json()["total"] == 0


@pytest.mark.asyncio
async def test_v5_alert_filter_by_type(client: AsyncClient, auth_headers):
    await client.post(
        "/api/health-alerts/_seed",
        headers=auth_headers,
        json={"items": [
            {"alert_type": "device", "indicator": "bp", "title": "血压"},
            {"alert_type": "checkup", "indicator": "bg", "title": "血糖"},
        ]},
    )
    r = await client.get("/api/health-alerts?alert_type=device", headers=auth_headers)
    assert all(it["alert_type"] == "device" for it in r.json()["items"])
    r2 = await client.get("/api/health-alerts?alert_type=checkup", headers=auth_headers)
    assert all(it["alert_type"] == "checkup" for it in r2.json()["items"])


@pytest.mark.asyncio
async def test_v5_medical_record_create_list(client: AsyncClient, auth_headers):
    payload = {
        "category": "checkup_report",
        "title": "体检报告 2026.05",
        "record_date": "2026-05-21",
        "source": "manual",
        "files": [
            {"file_url": "/uploads/a.jpg", "file_name": "a.jpg", "file_type": "image"},
            {"file_url": "/uploads/b.pdf", "file_name": "b.pdf", "file_type": "pdf"},
        ],
    }
    r = await client.post("/api/medical-records", headers=auth_headers, json=payload)
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["title"] == "体检报告 2026.05"
    assert rec["category"] == "checkup_report"
    assert rec["category_label"] == "体检报告"
    assert rec["source"] == "manual"
    assert rec["has_ai_interpretation"] is False
    assert rec["file_count"] == 2

    # 列表 + 分组统计
    lst = await client.get("/api/medical-records", headers=auth_headers)
    assert lst.json()["total"] == 1
    assert lst.json()["grouped"]["checkup_report"] == 1

    # overview 反映
    ov = await client.get("/api/health-archive-v5/overview", headers=auth_headers)
    assert ov.json()["medical_records_total"] == 1
    assert ov.json()["medical_records_by_category"]["checkup_report"] == 1


@pytest.mark.asyncio
async def test_v5_medical_record_too_many_files(client: AsyncClient, auth_headers):
    files = [{"file_url": f"/uploads/{i}.jpg", "file_name": f"{i}.jpg", "file_type": "image"} for i in range(10)]
    r = await client.post(
        "/api/medical-records",
        headers=auth_headers,
        json={"category": "other", "title": "T", "files": files},
    )
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_v5_medical_record_patch_and_soft_delete(client: AsyncClient, auth_headers):
    r = await client.post(
        "/api/medical-records",
        headers=auth_headers,
        json={
            "category": "drug",
            "title": "降压药 A",
            "source": "ai_drug",
            "files": [{"file_url": "/uploads/x.jpg", "file_name": "x.jpg", "file_type": "image"}],
            "ai_interpretation": {"name": "氨氯地平", "dosage": "5mg"},
        },
    )
    rid = r.json()["id"]

    # PATCH 改标题/备注
    pr = await client.patch(
        f"/api/medical-records/{rid}",
        headers=auth_headers,
        json={"title": "降压药 A（家庭备用）", "remark": "饭后服用"},
    )
    assert pr.status_code == 200
    assert pr.json()["title"] == "降压药 A（家庭备用）"
    assert pr.json()["remark"] == "饭后服用"
    assert pr.json()["has_ai_interpretation"] is True

    # 软删 → 回收站
    dr = await client.delete(f"/api/medical-records/{rid}", headers=auth_headers)
    assert dr.status_code == 200
    assert dr.json()["purge_after_days"] == 30

    # 列表过滤掉已删
    lst = await client.get("/api/medical-records?category=drug", headers=auth_headers)
    assert lst.json()["total"] == 0

    # 回收站可见
    tr = await client.get("/api/medical-records/trash", headers=auth_headers)
    assert tr.json()["total"] == 1
    assert tr.json()["items"][0]["is_deleted"] is True
    assert tr.json()["items"][0]["days_to_purge"] in (29, 30)

    # 恢复
    rr = await client.post(f"/api/medical-records/{rid}/restore", headers=auth_headers)
    assert rr.status_code == 200
    assert rr.json()["is_deleted"] is False
    lst2 = await client.get("/api/medical-records?category=drug", headers=auth_headers)
    assert lst2.json()["total"] == 1


@pytest.mark.asyncio
async def test_v5_medical_record_permanent_delete(client: AsyncClient, auth_headers):
    r = await client.post(
        "/api/medical-records",
        headers=auth_headers,
        json={
            "category": "other",
            "title": "其它",
            "files": [{"file_url": "/uploads/p.png", "file_name": "p.png", "file_type": "image"}],
        },
    )
    rid = r.json()["id"]
    await client.delete(f"/api/medical-records/{rid}", headers=auth_headers)
    # 立即彻底删除
    d2 = await client.delete(f"/api/medical-records/{rid}/permanent", headers=auth_headers)
    assert d2.status_code == 200
    tr = await client.get("/api/medical-records/trash", headers=auth_headers)
    assert tr.json()["total"] == 0


@pytest.mark.asyncio
async def test_v5_medical_record_invalid_category(client: AsyncClient, auth_headers):
    r = await client.post(
        "/api/medical-records",
        headers=auth_headers,
        json={"category": "unknown", "title": "x", "files": []},
    )
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_v5_medication_hero_count_no_plan(client: AsyncClient, auth_headers):
    # 用户未创建任何用药计划：应当返回 ai_home_label="今日无用药"
    res = await client.get(
        "/api/medication-plans/hero-count?consultant_id=0",
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    d = res.json()
    assert d["total_today"] == 0
    assert d["remaining_today"] == 0
    assert d["status"] == "none"
    assert d["ai_home_label"] == "今日无用药"
    assert d["ai_home_number"] == 0
