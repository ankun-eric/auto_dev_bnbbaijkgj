"""[PRD-469] 健康档案 v2 优化 —— 非UI自动化测试

覆盖：
  M3 - 关系选项 API + 自定义关系名重复校验
  M5 - 用药添加保存 Bug 修复（后端返回新对象 + 列表）
  M6 - 健康信息 GET/PUT
  M7 - 提醒规则 GET/PUT
  M8 - 健康事件时间轴 + 写日记
  M9 - 设备列表 10 项 + 敬请期待订阅
  M10 - 药品库联想搜索 + OCR
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient


# ─────────────────────── M3：关系选项 + 自定义校验 ────────────────────
@pytest.mark.asyncio
async def test_relation_options(client: AsyncClient):
    res = await client.get("/api/prd469/family-member/relation-options")
    assert res.status_code == 200
    data = res.json()
    items = data["items"]
    assert isinstance(items, list)
    assert len(items) >= 16
    names = {it["name"] for it in items}
    assert "本人" in names
    assert "爸爸" in names and "妈妈" in names
    assert "儿子" in names and "女儿" in names
    assert "其他" in names
    for it in items:
        assert "avatar" in it and len(it["avatar"]) > 0
    other = next(it for it in items if it["name"] == "其他")
    assert other["is_other"] is True


@pytest.mark.asyncio
async def test_relation_custom_check_conflict_with_preset(client: AsyncClient, auth_headers):
    """自定义关系名不能与预置关系名冲突。"""
    res = await client.post(
        "/api/prd469/family-member/relation-custom/check",
        json={"name": "爸爸"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    assert "冲突" in (data.get("reason") or "") or "已存在" in (data.get("reason") or "")


@pytest.mark.asyncio
async def test_relation_custom_check_valid(client: AsyncClient, auth_headers):
    res = await client.post(
        "/api/prd469/family-member/relation-custom/check",
        json={"name": "大儿子"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["valid"] is True


# ─────────────────────── M10：药品库 ────────────────────
@pytest_asyncio.fixture
async def seed_medications():
    """注入少量药品库种子，用于联想搜索测试。"""
    from app.models.models import MedicationLibrary
    from .conftest import test_session

    async with test_session() as session:
        session.add_all([
            MedicationLibrary(
                name="拜阿司匹灵", generic_name="阿司匹林肠溶片",
                spec="100mg*30片", manufacturer="拜耳",
                rx_type="非处方药", disease_tags=["心血管"], is_active=True,
            ),
            MedicationLibrary(
                name="拜唐苹", generic_name="阿卡波糖片",
                spec="50mg*30片", manufacturer="拜耳",
                rx_type="处方药", disease_tags=["糖尿病"], is_active=True,
            ),
            MedicationLibrary(
                name="二甲双胍片", generic_name="盐酸二甲双胍片",
                spec="0.5g*60片", manufacturer="默克",
                rx_type="处方药", disease_tags=["糖尿病"], is_active=True,
            ),
        ])
        await session.commit()


@pytest.mark.asyncio
async def test_medication_library_search(client: AsyncClient, seed_medications):
    """联想搜索：输入「阿」应能匹配到阿司匹林、阿卡波糖等。"""
    res = await client.get("/api/prd469/medication-library/search?kw=阿")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["items"], list)
    assert data["total"] >= 2
    names = [it["generic_name"] or it["name"] for it in data["items"]]
    assert any("阿司匹林" in n or "阿卡波糖" in n for n in names)


@pytest.mark.asyncio
async def test_medication_library_search_empty(client: AsyncClient):
    """空关键词返回空数组。"""
    res = await client.get("/api/prd469/medication-library/search?kw=")
    assert res.status_code == 200
    assert res.json()["total"] == 0


@pytest.mark.asyncio
async def test_medication_library_ocr_match(client: AsyncClient, seed_medications):
    """OCR 文字 + 库内匹配应能返回候选。"""
    res = await client.post(
        "/api/prd469/medication-library/ocr",
        json={"image_text": "请按医嘱服用 二甲双胍片 0.5g"},
    )
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_medication_library_ocr_empty_text(client: AsyncClient):
    res = await client.post("/api/prd469/medication-library/ocr", json={"image_text": ""})
    assert res.status_code == 200
    assert res.json()["total"] == 0


# ─────────────────────── M9：设备列表 ────────────────────
@pytest.mark.asyncio
async def test_device_list_has_10_items(client: AsyncClient, auth_headers):
    res = await client.get("/api/prd469/device/list", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    items = data["items"]
    assert len(items) == 10
    names = [it["name"] for it in items]
    assert "华为手环" in names
    huawei_band = next(it for it in items if it["name"] == "华为手环")
    assert huawei_band["status"] == "connected"
    others = [it for it in items if it["status"] == "coming_soon"]
    assert len(others) == 9


@pytest.mark.asyncio
async def test_device_subscribe(client: AsyncClient, auth_headers):
    res = await client.post(
        "/api/prd469/device/subscribe",
        json={"device_key": "apple_watch"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert "device_key" in res.json()


# ─────────────────────── M7：提醒规则 ────────────────────
@pytest.mark.asyncio
async def test_reminder_setting_default_and_update(client: AsyncClient, auth_headers):
    res = await client.get("/api/prd469/reminder-setting", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["miss_threshold_days"] == 3
    assert data["push_inapp"] is True

    res2 = await client.put(
        "/api/prd469/reminder-setting",
        json={"miss_threshold_days": 5, "silent_start": "22:00", "silent_end": "07:00"},
        headers=auth_headers,
    )
    assert res2.status_code == 200

    res3 = await client.get("/api/prd469/reminder-setting", headers=auth_headers)
    d3 = res3.json()
    assert d3["miss_threshold_days"] == 5
    assert d3["silent_start"] == "22:00"


# ─────────────────────── M8：健康事件 ────────────────────
@pytest_asyncio.fixture
async def user_profile_id(client: AsyncClient, auth_headers):
    """获取当前测试用户的 health_profile_id（注册时自动创建）。"""
    from app.models.models import HealthProfile, User
    from .conftest import test_session
    from sqlalchemy import select

    async with test_session() as session:
        user = (await session.execute(
            select(User).where(User.phone == "13900000001")
        )).scalar_one_or_none()
        assert user is not None
        # 创建一个 health_profile 以便后续测试
        hp = HealthProfile(user_id=user.id, name="测试用户")
        session.add(hp)
        await session.commit()
        return hp.id


@pytest.mark.asyncio
async def test_health_event_create_and_timeline(client: AsyncClient, auth_headers, user_profile_id):
    res = await client.post(
        "/api/prd469/health-event",
        json={
            "event_type": "diary",
            "title": "感冒就诊",
            "content": "下午发烧 38°C，去医院开了药",
            "event_date": "2026-05-12",
            "tags": ["不适"],
            "profile_id": user_profile_id,
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["id"] > 0

    res2 = await client.get("/api/prd469/health-event/timeline", headers=auth_headers)
    assert res2.status_code == 200
    items = res2.json()["items"]
    assert len(items) >= 1
    assert any(it["title"] == "感冒就诊" for it in items)


# ─────────────────────── M6：健康信息 ────────────────────
@pytest.mark.asyncio
async def test_health_info_get_and_update(client: AsyncClient, auth_headers, user_profile_id):
    res = await client.get(f"/api/prd469/health-info/{user_profile_id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["chronic_diseases"] == []
    assert data["drug_allergies"] == []

    res2 = await client.put(
        f"/api/prd469/health-info/{user_profile_id}",
        json={
            "chronic_diseases": [{"name": "高血压", "year": "2020"}],
            "drug_allergies": ["青霉素"],
            "habit_smoking": "无",
            "habit_drinking": "有",
            "habit_exercise": "经常",
            "habit_diet": "清淡",
        },
        headers=auth_headers,
    )
    assert res2.status_code == 200

    res3 = await client.get(f"/api/prd469/health-info/{user_profile_id}", headers=auth_headers)
    d3 = res3.json()
    assert d3["chronic_diseases"][0]["name"] == "高血压"
    assert "青霉素" in d3["drug_allergies"]
    assert d3["habit_smoking"] == "无"
    assert d3["habit_diet"] == "清淡"


@pytest.mark.asyncio
async def test_v5_summary_capsules(client: AsyncClient, auth_headers, user_profile_id):
    """胶囊摘要应包含习惯和慢病信息。"""
    await client.put(
        f"/api/prd469/health-info/{user_profile_id}",
        json={
            "chronic_diseases": [{"name": "高血压"}],
            "drug_allergies": ["青霉素"],
            "habit_smoking": "无",
        },
        headers=auth_headers,
    )
    res = await client.get(f"/api/prd469/summary/{user_profile_id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    capsules = data["capsules"]
    labels = " ".join(c["label"] for c in capsules)
    assert "不吸烟" in labels
    assert "高血压" in labels
    assert "青霉素" in labels


# ─────────────────────── M5：用药添加保存 Bug 修复回归 ──────────────
@pytest.mark.asyncio
async def test_medication_create_returns_full_object(client: AsyncClient, auth_headers):
    """添加用药计划保存接口应返回完整对象，前端据此即可乐观更新列表。"""
    res = await client.post(
        "/api/health-plan/medications",
        json={
            "medicine_name": "拜阿司匹灵",
            "dosage": "1片",
            "notes": "饭后服用",
            "time_period": "morning",
            "remind_time": "08:00",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("id", 0) > 0
    assert data["medicine_name"] == "拜阿司匹灵"
    # 紧接着请求列表 —— 必须能立即看到新条目（避免数据库延迟问题）
    res2 = await client.get("/api/health-plan/medications", headers=auth_headers)
    assert res2.status_code == 200
    groups = res2.json().get("groups") or {}
    names = []
    for items in groups.values():
        for it in items:
            names.append(it.get("medicine_name"))
    assert "拜阿司匹灵" in names
