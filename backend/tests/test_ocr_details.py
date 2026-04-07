import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    AiPromptConfig,
    CheckupReportDetail,
    DrugIdentifyDetail,
    OcrCallRecord,
)
from tests.conftest import test_session


async def _seed_checkup_details(count=3):
    async with test_session() as session:
        for i in range(count):
            record = OcrCallRecord(
                scene_name="体检报告识别",
                provider_name="baidu",
                status="success",
                ocr_raw_text=f"体检报告文字{i}",
                ai_structured_result={"report_type": "血常规", "summary": f"摘要{i}"},
            )
            session.add(record)
            await session.flush()

            detail = CheckupReportDetail(
                user_id=None,
                user_phone="13812345678",
                user_nickname=f"用户{i}",
                report_type="血常规" if i % 2 == 0 else "肝功能",
                abnormal_count=i,
                summary=f"解读摘要{i}",
                status="abnormal" if i > 0 else "normal",
                provider_name="baidu",
                original_image_url=f"http://example.com/img{i}.jpg",
                ocr_raw_text=f"体检报告文字{i}",
                ai_structured_result={"report_type": "血常规"},
                abnormal_indicators=[{"name": "白细胞", "value": "12.5"}] if i > 0 else None,
                ocr_call_record_id=record.id,
            )
            session.add(detail)
        await session.commit()


async def _seed_drug_details(count=3):
    async with test_session() as session:
        drugs = ["阿莫西林", "布洛芬", "板蓝根"]
        categories = ["处方药", "非处方药", "中成药"]
        for i in range(count):
            record = OcrCallRecord(
                scene_name="拍照识药",
                provider_name="tencent",
                status="success",
                ocr_raw_text=f"药品说明书{i}",
                ai_structured_result={"drug_name": drugs[i % 3]},
            )
            session.add(record)
            await session.flush()

            detail = DrugIdentifyDetail(
                user_id=None,
                user_phone="13987654321",
                user_nickname=f"药品用户{i}",
                drug_name=drugs[i % 3],
                drug_category=categories[i % 3],
                dosage=f"每日{i+1}次",
                precautions=f"注意事项{i}",
                provider_name="tencent",
                original_image_url=f"http://example.com/drug{i}.jpg",
                ocr_raw_text=f"药品说明书{i}",
                ai_structured_result={"drug_name": drugs[i % 3]},
                ocr_call_record_id=record.id,
            )
            session.add(detail)
        await session.commit()


# ──── Checkup Details Tests ────


@pytest.mark.asyncio
async def test_checkup_statistics_empty(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/checkup-details/statistics", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["today_count"] == 0
    assert data["abnormal_count"] == 0
    assert data["month_count"] == 0


@pytest.mark.asyncio
async def test_checkup_statistics_with_data(client: AsyncClient, admin_headers):
    await _seed_checkup_details(3)
    resp = await client.get("/api/admin/checkup-details/statistics", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["today_count"] == 3
    assert data["abnormal_count"] == 2
    assert data["month_count"] == 3


@pytest.mark.asyncio
async def test_checkup_list(client: AsyncClient, admin_headers):
    await _seed_checkup_details(3)
    resp = await client.get("/api/admin/checkup-details", headers=admin_headers, params={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    item = data["items"][0]
    assert "user_phone" in item
    assert "****" in (item["user_phone"] or "")


@pytest.mark.asyncio
async def test_checkup_list_filter_status(client: AsyncClient, admin_headers):
    await _seed_checkup_details(3)
    resp = await client.get("/api/admin/checkup-details", headers=admin_headers, params={"status": "normal"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_checkup_list_filter_report_type(client: AsyncClient, admin_headers):
    await _seed_checkup_details(3)
    resp = await client.get("/api/admin/checkup-details", headers=admin_headers, params={"report_type": "血常规"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_checkup_list_filter_keyword(client: AsyncClient, admin_headers):
    await _seed_checkup_details(3)
    resp = await client.get("/api/admin/checkup-details", headers=admin_headers, params={"keyword": "138"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_checkup_detail(client: AsyncClient, admin_headers):
    await _seed_checkup_details(1)
    list_resp = await client.get("/api/admin/checkup-details", headers=admin_headers)
    item_id = list_resp.json()["items"][0]["id"]

    resp = await client.get(f"/api/admin/checkup-details/{item_id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == item_id
    assert data["user_phone"] == "13812345678"


@pytest.mark.asyncio
async def test_checkup_detail_not_found(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/checkup-details/99999", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_checkup_no_auth(client: AsyncClient):
    resp = await client.get("/api/admin/checkup-details/statistics")
    assert resp.status_code in (401, 403)


# ──── Drug Details Tests ────


@pytest.mark.asyncio
async def test_drug_statistics_empty(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/drug-details/statistics", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["today_count"] == 0
    assert data["drug_types_count"] == 0
    assert data["month_count"] == 0


@pytest.mark.asyncio
async def test_drug_statistics_with_data(client: AsyncClient, admin_headers):
    await _seed_drug_details(3)
    resp = await client.get("/api/admin/drug-details/statistics", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["today_count"] == 3
    assert data["drug_types_count"] == 3
    assert data["month_count"] == 3


@pytest.mark.asyncio
async def test_drug_list(client: AsyncClient, admin_headers):
    await _seed_drug_details(3)
    resp = await client.get("/api/admin/drug-details", headers=admin_headers, params={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    item = data["items"][0]
    assert "****" in (item["user_phone"] or "")


@pytest.mark.asyncio
async def test_drug_list_filter_name(client: AsyncClient, admin_headers):
    await _seed_drug_details(3)
    resp = await client.get("/api/admin/drug-details", headers=admin_headers, params={"drug_name": "阿莫西林"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_drug_list_filter_category(client: AsyncClient, admin_headers):
    await _seed_drug_details(3)
    resp = await client.get("/api/admin/drug-details", headers=admin_headers, params={"drug_category": "中成药"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_drug_detail(client: AsyncClient, admin_headers):
    await _seed_drug_details(1)
    list_resp = await client.get("/api/admin/drug-details", headers=admin_headers)
    item_id = list_resp.json()["items"][0]["id"]

    resp = await client.get(f"/api/admin/drug-details/{item_id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == item_id
    assert data["user_phone"] == "13987654321"
    assert data["drug_name"] is not None


@pytest.mark.asyncio
async def test_drug_detail_not_found(client: AsyncClient, admin_headers):
    resp = await client.get("/api/admin/drug-details/99999", headers=admin_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_drug_no_auth(client: AsyncClient):
    resp = await client.get("/api/admin/drug-details/statistics")
    assert resp.status_code in (401, 403)


# ──── OCR Prompt Config in AI Center ────


@pytest.mark.asyncio
async def test_ocr_prompt_configs_accessible(client: AsyncClient, admin_headers):
    async with test_session() as session:
        session.add(AiPromptConfig(
            chat_type="ocr_checkup_report",
            display_name="体检报告识别",
            system_prompt="test prompt",
        ))
        session.add(AiPromptConfig(
            chat_type="ocr_drug_identify",
            display_name="拍照识药",
            system_prompt="test drug prompt",
        ))
        await session.commit()

    resp = await client.get("/api/admin/ai-center/prompts", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    items = data.get("items", data if isinstance(data, list) else [])
    chat_types = [i["chat_type"] for i in items]
    assert "ocr_checkup_report" in chat_types
    assert "ocr_drug_identify" in chat_types


@pytest.mark.asyncio
async def test_ocr_prompt_update(client: AsyncClient, admin_headers):
    async with test_session() as session:
        session.add(AiPromptConfig(
            chat_type="ocr_checkup_report",
            display_name="体检报告识别",
            system_prompt="old prompt",
        ))
        await session.commit()

    resp = await client.put(
        "/api/admin/ai-center/prompts/ocr_checkup_report",
        headers=admin_headers,
        json={"system_prompt": "new checkup prompt"},
    )
    assert resp.status_code == 200
    assert resp.json()["system_prompt"] == "new checkup prompt"
