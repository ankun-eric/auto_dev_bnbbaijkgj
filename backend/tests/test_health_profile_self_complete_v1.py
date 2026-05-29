"""[PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 本人健康档案完善 接口测试

覆盖：
- GET /api/health-profile/self：needComplete / missingFields 计算
- PUT /api/health-profile/self：三项必填校验、占位文案视为空、保存后 needComplete=false
"""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import test_session
from app.core.security import get_password_hash
from app.models.models import FamilyMember, HealthProfile, User, UserRole


# ─────────── 工具 ───────────


async def _make_user(phone: str, nickname: str = "用户") -> int:
    async with test_session() as s:
        u = User(
            phone=phone,
            password_hash=get_password_hash("p123"),
            nickname=nickname,
            role=UserRole.user,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        # 同时建一条 is_self FamilyMember，模拟真实注册流程
        fm = FamilyMember(
            user_id=uid,
            relationship_type="本人",
            nickname="本人",
            is_self=True,
            status="active",
        )
        s.add(fm)
        await s.commit()
        return uid


async def _login(client: AsyncClient, phone: str) -> str:
    res = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "p123"}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


async def _headers(client: AsyncClient, phone: str) -> dict:
    token = await _login(client, phone)
    return {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}


# ─────────── GET：needComplete / missingFields ───────────


@pytest.mark.asyncio
async def test_get_self_returns_need_complete_when_no_profile(client: AsyncClient):
    """新注册用户：无 HealthProfile 记录 → needComplete=true, missingFields=三项"""
    await _make_user("13980000001")
    headers = await _headers(client, "13980000001")
    r = await client.get("/api/health-profile/self", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["needComplete"] is True
    assert set(data["missingFields"]) == {"name", "gender", "birthday"}
    assert data["name"] == "本人"


@pytest.mark.asyncio
async def test_get_self_placeholder_name_is_empty(client: AsyncClient):
    """name=="本人" 占位文案 视为空，needComplete=true 仍包含 name"""
    uid = await _make_user("13980000002")
    async with test_session() as s:
        hp = HealthProfile(
            user_id=uid,
            family_member_id=None,
            name="本人",
            gender="男",
            birthday=date(1990, 1, 1),
        )
        s.add(hp)
        await s.commit()
    headers = await _headers(client, "13980000002")
    r = await client.get("/api/health-profile/self", headers=headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["needComplete"] is True
    assert "name" in data["missingFields"]
    assert "gender" not in data["missingFields"]
    assert "birthday" not in data["missingFields"]


@pytest.mark.asyncio
async def test_get_self_partial_missing(client: AsyncClient):
    """部分缺失：missingFields 只包含实际缺失的字段"""
    uid = await _make_user("13980000003")
    async with test_session() as s:
        hp = HealthProfile(
            user_id=uid,
            family_member_id=None,
            name="张三",
            gender=None,
            birthday=None,
        )
        s.add(hp)
        await s.commit()
    headers = await _headers(client, "13980000003")
    r = await client.get("/api/health-profile/self", headers=headers)
    data = r.json()["data"]
    assert data["needComplete"] is True
    assert set(data["missingFields"]) == {"gender", "birthday"}


@pytest.mark.asyncio
async def test_get_self_all_filled_no_need_complete(client: AsyncClient):
    """三项都已填 → needComplete=false, missingFields=[]"""
    uid = await _make_user("13980000004")
    async with test_session() as s:
        hp = HealthProfile(
            user_id=uid,
            family_member_id=None,
            name="李四",
            gender="女",
            birthday=date(1985, 6, 15),
        )
        s.add(hp)
        await s.commit()
    headers = await _headers(client, "13980000004")
    r = await client.get("/api/health-profile/self", headers=headers)
    data = r.json()["data"]
    assert data["needComplete"] is False
    assert data["missingFields"] == []
    assert data["name"] == "李四"


# ─────────── PUT：三项必填校验 ───────────


@pytest.mark.asyncio
async def test_put_self_missing_name_returns_400(client: AsyncClient):
    """缺少 name → 400 + field_errors"""
    await _make_user("13980000011")
    headers = await _headers(client, "13980000011")
    r = await client.put(
        "/api/health-profile/self",
        headers=headers,
        json={"gender": "男", "birthday": "1990-01-01"},
    )
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "field_errors" in detail
    assert "name" in detail["field_errors"]


@pytest.mark.asyncio
async def test_put_self_placeholder_name_returns_400(client: AsyncClient):
    """name=='本人' 被视为空 → 400"""
    await _make_user("13980000012")
    headers = await _headers(client, "13980000012")
    r = await client.put(
        "/api/health-profile/self",
        headers=headers,
        json={"name": "本人", "gender": "男", "birthday": "1990-01-01"},
    )
    assert r.status_code == 400
    assert "name" in r.json()["detail"]["field_errors"]


@pytest.mark.asyncio
async def test_put_self_missing_gender_returns_400(client: AsyncClient):
    await _make_user("13980000013")
    headers = await _headers(client, "13980000013")
    r = await client.put(
        "/api/health-profile/self",
        headers=headers,
        json={"name": "张三", "birthday": "1990-01-01"},
    )
    assert r.status_code == 400
    assert "gender" in r.json()["detail"]["field_errors"]


@pytest.mark.asyncio
async def test_put_self_missing_birthday_returns_400(client: AsyncClient):
    await _make_user("13980000014")
    headers = await _headers(client, "13980000014")
    r = await client.put(
        "/api/health-profile/self",
        headers=headers,
        json={"name": "张三", "gender": "男"},
    )
    assert r.status_code == 400
    assert "birthday" in r.json()["detail"]["field_errors"]


@pytest.mark.asyncio
async def test_put_self_birthday_future_returns_400(client: AsyncClient):
    """出生日期不能晚于今天"""
    await _make_user("13980000015")
    headers = await _headers(client, "13980000015")
    r = await client.put(
        "/api/health-profile/self",
        headers=headers,
        json={"name": "张三", "gender": "男", "birthday": "2099-01-01"},
    )
    assert r.status_code == 400
    assert "birthday" in r.json()["detail"]["field_errors"]


@pytest.mark.asyncio
async def test_put_self_birthday_too_old_returns_400(client: AsyncClient):
    """出生日期不能早于 1900-01-01"""
    await _make_user("13980000016")
    headers = await _headers(client, "13980000016")
    r = await client.put(
        "/api/health-profile/self",
        headers=headers,
        json={"name": "张三", "gender": "男", "birthday": "1899-12-31"},
    )
    assert r.status_code == 400
    assert "birthday" in r.json()["detail"]["field_errors"]


# ─────────── PUT：成功保存 ───────────


@pytest.mark.asyncio
async def test_put_self_success_sets_need_complete_false(client: AsyncClient):
    """三项都填齐 → 200，且 needComplete=false"""
    await _make_user("13980000021")
    headers = await _headers(client, "13980000021")
    r = await client.put(
        "/api/health-profile/self",
        headers=headers,
        json={
            "name": "王五",
            "gender": "男",
            "birthday": "1992-03-08",
            "height": 175,
            "weight": 70,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["needComplete"] is False
    assert body["data"]["missingFields"] == []
    assert body["data"]["profile"]["name"] == "王五"
    assert body["data"]["profile"]["gender"] == "男"


@pytest.mark.asyncio
async def test_put_self_success_then_get_no_need_complete(client: AsyncClient):
    """保存成功后，再次 GET 应该 needComplete=false"""
    await _make_user("13980000022")
    headers = await _headers(client, "13980000022")
    await client.put(
        "/api/health-profile/self",
        headers=headers,
        json={"name": "赵六", "gender": "女", "birthday": "1988-12-12"},
    )
    r = await client.get("/api/health-profile/self", headers=headers)
    data = r.json()["data"]
    assert data["needComplete"] is False
    assert data["name"] == "赵六"


@pytest.mark.asyncio
async def test_put_self_updates_family_member_nickname(client: AsyncClient):
    """[PRD §5.4.3] 保存成功后，本人 FamilyMember.nickname 从"本人"变为真实姓名"""
    uid = await _make_user("13980000023")
    headers = await _headers(client, "13980000023")
    await client.put(
        "/api/health-profile/self",
        headers=headers,
        json={"name": "孙七", "gender": "男", "birthday": "1995-05-20"},
    )
    async with test_session() as s:
        result = await s.execute(
            select(FamilyMember).where(
                FamilyMember.user_id == uid, FamilyMember.is_self.is_(True)
            )
        )
        fm = result.scalar_one()
        assert fm.nickname == "孙七"
        assert fm.gender == "男"


@pytest.mark.asyncio
async def test_put_self_idempotent_update(client: AsyncClient):
    """重复 PUT 同一份数据，应返回 200 且保持数据一致"""
    await _make_user("13980000024")
    headers = await _headers(client, "13980000024")
    payload = {"name": "周八", "gender": "女", "birthday": "1990-07-07"}
    r1 = await client.put("/api/health-profile/self", headers=headers, json=payload)
    assert r1.status_code == 200
    r2 = await client.put("/api/health-profile/self", headers=headers, json=payload)
    assert r2.status_code == 200
    assert r2.json()["data"]["needComplete"] is False


@pytest.mark.asyncio
async def test_put_self_with_english_gender_normalizes(client: AsyncClient):
    """gender 接受 male/female 并归一化为中文 男/女"""
    await _make_user("13980000025")
    headers = await _headers(client, "13980000025")
    r = await client.put(
        "/api/health-profile/self",
        headers=headers,
        json={"name": "吴九", "gender": "male", "birthday": "1991-01-01"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["profile"]["gender"] == "男"


# ─────────── 未鉴权场景 ───────────


@pytest.mark.asyncio
async def test_get_self_requires_auth(client: AsyncClient):
    r = await client.get("/api/health-profile/self")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_put_self_requires_auth(client: AsyncClient):
    r = await client.put(
        "/api/health-profile/self",
        json={"name": "x", "gender": "男", "birthday": "1990-01-01"},
    )
    assert r.status_code in (401, 403)


# ─────────── [BUG_FIX 2026-05-29] 旧用户兼容 / 跨表并集判定 ───────────
# 关联文档：docs/BUG_FIX_健康档案本人资料完善弹窗误弹与旧用户兼容_20260529.md
# 修复策略 C：数据回填 + 放宽判定逻辑（双保险）


@pytest.mark.asyncio
async def test_new_02_legacy_user_only_family_member_self(client: AsyncClient):
    """TC-NEW-02：旧用户只有 family_members(is_self=1) 上的 nickname/gender/birthday，
    health_profiles 没有 self 记录 → needComplete=false（v2 兜底）"""
    async with test_session() as s:
        u = User(
            phone="13980000101",
            password_hash=get_password_hash("p123"),
            nickname="老用户",
            role=UserRole.user,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        s.add(FamilyMember(
            user_id=uid,
            relationship_type="本人",
            nickname="陈旧",
            gender="男",
            birthday=date(1980, 1, 1),
            is_self=True,
            status="active",
        ))
        await s.commit()
    headers = await _headers(client, "13980000101")
    r = await client.get("/api/health-profile/self", headers=headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["needComplete"] is False, data
    assert data["missingFields"] == []


@pytest.mark.asyncio
async def test_new_03_legacy_user_partial_in_two_tables(client: AsyncClient):
    """TC-NEW-03（项目调整版）：health_profiles 仅有 name/gender，birthday 缺失，
    family_members(is_self=1) 上有 birthday → 跨表并集判定为已完善"""
    async with test_session() as s:
        u = User(
            phone="13980000102",
            password_hash=get_password_hash("p123"),
            nickname="混合用户",
            role=UserRole.user,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        s.add(FamilyMember(
            user_id=uid,
            relationship_type="本人",
            nickname="周混合",
            birthday=date(1975, 6, 6),
            is_self=True,
            status="active",
        ))
        s.add(HealthProfile(
            user_id=uid,
            family_member_id=None,
            name="周混合",
            gender="男",
            birthday=None,
        ))
        await s.commit()
    headers = await _headers(client, "13980000102")
    r = await client.get("/api/health-profile/self", headers=headers)
    data = r.json()["data"]
    assert data["needComplete"] is False, data
    assert data["missingFields"] == []


@pytest.mark.asyncio
async def test_new_04_other_members_incomplete_self_complete(client: AsyncClient):
    """TC-NEW-04：用户有多个非 self 成员，本人档案齐全 → needComplete=false（与其他成员无关）"""
    async with test_session() as s:
        u = User(
            phone="13980000103",
            password_hash=get_password_hash("p123"),
            nickname="多成员用户",
            role=UserRole.user,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        s.add(FamilyMember(
            user_id=uid, relationship_type="本人", nickname="本人",
            is_self=True, status="active",
        ))
        for i, rel in enumerate(["父亲", "母亲", "儿子"]):
            s.add(FamilyMember(
                user_id=uid, relationship_type=rel,
                nickname=f"家人{i}", is_self=False, status="active",
            ))
        s.add(HealthProfile(
            user_id=uid, family_member_id=None,
            name="本人姓名", gender="女", birthday=date(1990, 5, 5),
        ))
        await s.commit()
    headers = await _headers(client, "13980000103")
    r = await client.get("/api/health-profile/self", headers=headers)
    data = r.json()["data"]
    assert data["needComplete"] is False, data
    assert data["missingFields"] == []


@pytest.mark.asyncio
async def test_new_05_other_members_incomplete_self_missing_name(client: AsyncClient):
    """TC-NEW-05：本人档案缺 name（且 family_members(is_self) 也是占位"本人"），其他成员未完善
    → needComplete=true，missingFields=["name"]"""
    async with test_session() as s:
        u = User(
            phone="13980000104",
            password_hash=get_password_hash("p123"),
            nickname="x",
            role=UserRole.user,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        s.add(FamilyMember(
            user_id=uid, relationship_type="本人", nickname="本人",
            is_self=True, status="active",
        ))
        s.add(FamilyMember(
            user_id=uid, relationship_type="父亲", nickname="父",
            is_self=False, status="active",
        ))
        s.add(HealthProfile(
            user_id=uid, family_member_id=None,
            name="本人", gender="男", birthday=date(1990, 5, 5),
        ))
        await s.commit()
    headers = await _headers(client, "13980000104")
    r = await client.get("/api/health-profile/self", headers=headers)
    data = r.json()["data"]
    assert data["needComplete"] is True
    assert data["missingFields"] == ["name"]


@pytest.mark.asyncio
async def test_new_06_brand_new_user_all_missing(client: AsyncClient):
    """TC-NEW-06：全新用户，无任何资料 → needComplete=true，三项 missing"""
    await _make_user("13980000105")
    headers = await _headers(client, "13980000105")
    r = await client.get("/api/health-profile/self", headers=headers)
    data = r.json()["data"]
    assert data["needComplete"] is True
    assert set(data["missingFields"]) == {"name", "gender", "birthday"}


@pytest.mark.asyncio
async def test_new_07_backfill_idempotent(client: AsyncClient):
    """TC-NEW-07：数据回填迁移幂等性——执行两次结果一致"""
    async with test_session() as s:
        u = User(
            phone="13980000106",
            password_hash=get_password_hash("p123"),
            nickname="回填",
            role=UserRole.user,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        s.add(FamilyMember(
            user_id=uid, relationship_type="本人", nickname="郑回填",
            gender="女", birthday=date(1985, 8, 8),
            is_self=True, status="active",
        ))
        await s.commit()

    # 直接复用迁移脚本里的 backfill 函数进行幂等执行
    import importlib.util as _ilu
    import os as _os
    mig_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        "migrations",
        "20260529_backfill_self_profile.py",
    )
    spec = _ilu.spec_from_file_location("_backfill_self", mig_path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    s1 = await mod.backfill()
    s2 = await mod.backfill()
    assert s2["created"] == 0  # 第二次不应再 create
    assert s2["updated"] == 0  # 第二次也不应再 update（已齐全）

    headers = await _headers(client, "13980000106")
    r = await client.get("/api/health-profile/self", headers=headers)
    data = r.json()["data"]
    assert data["needComplete"] is False, data


@pytest.mark.asyncio
async def test_new_08_placeholder_only_no_real_data(client: AsyncClient):
    """TC-NEW-08：family_members(is_self=1) 的 nickname 为占位"本人"且其他都没数据
    → needComplete=true（占位文案视为空，并集仍补不齐 name）"""
    async with test_session() as s:
        u = User(
            phone="13980000107",
            password_hash=get_password_hash("p123"),
            nickname="占位",
            role=UserRole.user,
        )
        s.add(u)
        await s.flush()
        uid = u.id
        s.add(FamilyMember(
            user_id=uid, relationship_type="本人", nickname="本人",
            is_self=True, status="active",
        ))
        await s.commit()
    headers = await _headers(client, "13980000107")
    r = await client.get("/api/health-profile/self", headers=headers)
    data = r.json()["data"]
    assert data["needComplete"] is True
    assert "name" in data["missingFields"]
