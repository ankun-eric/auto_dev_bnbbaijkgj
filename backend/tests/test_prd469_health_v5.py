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


# ─────────────────── [PRD-469 v2 P0] 新增字段回归 ─────────────────


@pytest.mark.asyncio
async def test_medication_create_with_new_p0_fields(client: AsyncClient, auth_headers):
    """[PRD-469 v2 P0 M4] 添加用药支持每日次数 / 自定义时间点 / 起止日期 / 长期 / 提醒开关 / 关联疾病。"""
    res = await client.post(
        "/api/health-plan/medications",
        json={
            "medicine_name": "二甲双胍",
            "dosage": "0.5g",
            "notes": "餐后",
            "frequency_per_day": 3,
            "custom_times": ["08:00", "12:30", "20:00"],
            "start_date": "2026-05-13",
            "long_term": True,
            "reminder_enabled": True,
            "disease_tags": ["糖尿病", "高血压"],
        },
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["medicine_name"] == "二甲双胍"
    assert data.get("frequency_per_day") == 3
    assert data.get("custom_times") == ["08:00", "12:30", "20:00"]
    assert data.get("long_term") is True
    assert data.get("reminder_enabled") is True
    assert "糖尿病" in (data.get("disease_tags") or [])


@pytest.mark.asyncio
async def test_medication_update_p0_fields(client: AsyncClient, auth_headers):
    """[PRD-469 v2 P0 M4] 编辑保留并更新 P0 字段。"""
    create_res = await client.post(
        "/api/health-plan/medications",
        json={
            "medicine_name": "卡托普利",
            "dosage": "1片",
            "frequency_per_day": 2,
            "custom_times": ["08:00", "20:00"],
            "long_term": False,
            "start_date": "2026-05-13",
            "end_date": "2026-08-13",
            "disease_tags": ["高血压"],
        },
        headers=auth_headers,
    )
    mid = create_res.json()["id"]
    upd = await client.put(
        f"/api/health-plan/medications/{mid}",
        json={
            "frequency_per_day": 1,
            "custom_times": ["09:00"],
            "long_term": True,
            "reminder_enabled": False,
        },
        headers=auth_headers,
    )
    assert upd.status_code == 200, upd.text
    d = upd.json()
    assert d.get("frequency_per_day") == 1
    assert d.get("custom_times") == ["09:00"]
    assert d.get("long_term") is True
    assert d.get("reminder_enabled") is False


@pytest.mark.asyncio
async def test_hero_summary_metrics(client: AsyncClient, auth_headers, user_profile_id):
    """[PRD-469 v2 P1] /summary/{profile_id} 返回四格 Hero 指标。"""
    profile_id = user_profile_id
    # 准备：写入慢病、过敏、家族史
    await client.put(
        f"/api/prd469/health-info/{profile_id}",
        json={
            "chronic_diseases": [{"name": "高血压"}, {"name": "糖尿病"}],
            "drug_allergies": ["青霉素"],
            "food_allergies": ["海鲜"],
            "family_history": [{"relation": "父亲", "disease": "高血压"}],
        },
        headers=auth_headers,
    )
    await client.post(
        "/api/health-plan/medications",
        json={"medicine_name": "降压药A", "dosage": "1片"},
        headers=auth_headers,
    )

    res = await client.get(f"/api/prd469/summary/{profile_id}", headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    hero = data.get("hero_metrics") or []
    assert len(hero) == 4
    labels = {m["label"]: m["count"] for m in hero}
    assert labels.get("既往病史", 0) >= 2
    assert labels.get("过敏史", 0) >= 2
    assert labels.get("家族遗传", 0) >= 1
    # [BUG-HEALTH-ARCHIVE-V2 2026-05-16] 第 4 格 label 改为「在用药品」
    assert labels.get("在用药品", 0) >= 1


# ─────────────────── [PRD-469 v2 P0 M8] 病历卡 + OCR ─────────────────


@pytest.mark.asyncio
async def test_medical_record_create_with_ocr_text(client: AsyncClient, auth_headers, user_profile_id):
    """病历卡创建时通过 OCR 文本自动解析关键字段。"""
    profile_id = user_profile_id
    ocr_text = (
        "上海第六人民医院\n"
        "内科门诊\n"
        "就诊日期：2026-04-12\n"
        "诊断：原发性高血压（2级）\n"
        "处方医师：王医师\n"
        "处方：苯磺酸氨氯地平 5mg 每日 1 次"
    )
    res = await client.post(
        "/api/prd469/medical-record",
        json={
            "profile_id": profile_id,
            "ocr_text": ocr_text,
            "image_url": "https://example.com/test.jpg",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["id"] > 0
    assert data["event_id"] > 0
    assert data.get("parse_status") == "parsed"
    # 解析字段
    assert "医院" in (data.get("parsed_hospital") or "")
    assert "诊断" in (data.get("parsed_diagnosis") or "") or "高血压" in (data.get("parsed_diagnosis") or "")
    assert data.get("parsed_visit_date") == "2026-04-12"


@pytest.mark.asyncio
async def test_medical_record_list_and_delete(client: AsyncClient, auth_headers, user_profile_id):
    """病历卡列表 + 删除。"""
    profile_id = user_profile_id
    # 先创建一条
    create_res = await client.post(
        "/api/prd469/medical-record",
        json={
            "profile_id": profile_id,
            "ocr_text": "测试医院\n2026-05-01 \n诊断：感冒",
        },
        headers=auth_headers,
    )
    rid = create_res.json()["id"]

    # 列表
    list_res = await client.get(
        f"/api/prd469/medical-record/list?profile_id={profile_id}",
        headers=auth_headers,
    )
    assert list_res.status_code == 200
    items = list_res.json().get("items") or []
    assert any(it["id"] == rid for it in items)

    # 删除
    del_res = await client.delete(
        f"/api/prd469/medical-record/{rid}", headers=auth_headers
    )
    assert del_res.status_code == 200


@pytest.mark.asyncio
async def test_medical_record_creates_health_event(client: AsyncClient, auth_headers, user_profile_id):
    """病历卡创建应自动同步一条 health_event 进入时间轴。"""
    profile_id = user_profile_id
    res = await client.post(
        "/api/prd469/medical-record",
        json={
            "profile_id": profile_id,
            "ocr_text": "测试病历卡\n2026-05-10\n诊断：测试",
        },
        headers=auth_headers,
    )
    assert res.status_code == 200
    # 查询时间轴是否含 upload 事件
    tl = await client.get(
        f"/api/prd469/health-event/timeline?profile_id={profile_id}",
        headers=auth_headers,
    )
    assert tl.status_code == 200
    items = tl.json().get("items") or []
    has_upload = any(it["event_type"] == "upload" for it in items)
    assert has_upload, "病历卡上传后应在健康事件时间轴出现 upload 事件"


@pytest.mark.asyncio
async def test_medical_record_404(client: AsyncClient, auth_headers):
    """不存在的病历卡返回 404。"""
    res = await client.get("/api/prd469/medical-record/999999", headers=auth_headers)
    assert res.status_code == 404


# ─────────────────── [PRD-469 v2 P0 M6] 健康信息：家族病史 + 手术史 ──


@pytest.mark.asyncio
async def test_health_info_family_history_and_surgery(client: AsyncClient, auth_headers, user_profile_id):
    """健康信息 PUT 应能接收家族病史 + 手术史 + 慢病确诊年份。"""
    profile_id = user_profile_id
    payload = {
        "chronic_diseases": [
            {"name": "高血压", "year": "2018"},
            {"name": "糖尿病", "year": "2020"},
        ],
        "surgery_history": [
            {"name": "阑尾切除术", "time": "2015-06", "note": "上海仁济医院"},
        ],
        "family_history": [
            {"relation": "父亲", "disease": "高血压"},
            {"relation": "母亲", "disease": "糖尿病"},
        ],
    }
    res = await client.put(
        f"/api/prd469/health-info/{profile_id}",
        json=payload,
        headers=auth_headers,
    )
    assert res.status_code == 200

    get_res = await client.get(
        f"/api/prd469/health-info/{profile_id}", headers=auth_headers
    )
    assert get_res.status_code == 200
    d = get_res.json()
    chronic = d.get("chronic_diseases") or []
    assert any(c.get("name") == "高血压" and c.get("year") == "2018" for c in chronic)
    surgery = d.get("surgery_history") or []
    assert any(s.get("name") == "阑尾切除术" for s in surgery)
    fam = d.get("family_history") or []
    assert any(f.get("relation") == "父亲" and f.get("disease") == "高血压" for f in fam)
    assert any(f.get("relation") == "母亲" and f.get("disease") == "糖尿病" for f in fam)
