"""[PRD-FAMILY-MEMBER-V2 2026-05-18] 家庭成员模块重构后端兼容性测试

本期重构是前端为主（关系唯一性、合理性硬校验、字徽、年龄展示）。
后端 API 未做大改，本测试验证：
  - 新表单提交的全部字段（含身高/体重/既往病史/过敏史）都可正确落库
  - 关系名为 PRD 规定的中文（爸爸/妈妈/老公/老婆/...）时可正常保存
  - 「其他」自定义关系名可保存
  - 列表接口返回 birthday + gender + relationship_type（供前端字徽 + 年龄计算）
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_family_v2_chinese_relation_save(client: AsyncClient, auth_headers):
    """PRD 中文关系（爸爸/妈妈/儿子...）可保存"""
    for relation in ["爸爸", "妈妈", "老公", "老婆", "儿子", "女儿", "哥哥", "姐姐", "弟弟", "妹妹", "爷爷", "奶奶", "外公", "外婆"]:
        resp = await client.post("/api/family/members", json={
            "relationship_type": relation,
            "name": f"测试{relation}",
            "nickname": f"测试{relation}",
            "gender": "male" if relation in ("爸爸", "老公", "儿子", "哥哥", "弟弟", "爷爷", "外公") else "female",
            "birthday": "1960-01-01" if relation in ("爸爸", "妈妈", "爷爷", "奶奶", "外公", "外婆") else "2010-01-01",
        }, headers=auth_headers)
        assert resp.status_code == 200, f"{relation} should save successfully: {resp.text}"
        data = resp.json()
        assert data["relationship_type"] == relation
        assert data["nickname"] == f"测试{relation}"


@pytest.mark.asyncio
async def test_family_v2_other_custom_relation(client: AsyncClient, auth_headers):
    """『其他』自定义关系名可保存"""
    resp = await client.post("/api/family/members", json={
        "relationship_type": "舅舅",
        "name": "我的舅舅",
        "nickname": "我的舅舅",
        "gender": "male",
        "birthday": "1965-08-15",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["relationship_type"] == "舅舅"


@pytest.mark.asyncio
async def test_family_v2_full_payload(client: AsyncClient, auth_headers):
    """新表单完整字段都可落库"""
    resp = await client.post("/api/family/members", json={
        "relationship_type": "爸爸",
        "name": "我爸",
        "nickname": "我爸",
        "gender": "male",
        "birthday": "1965-01-01",
        "height": 175.5,
        "weight": 70.2,
        "medical_histories": ["高血压", "糖尿病"],
        # 后端 schema 中 allergies 为 List[str]，新前端会按 "药物:青霉素" 形态合并
        "allergies": ["药物:青霉素", "食物:海鲜"],
    }, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["height"] == 175.5
    assert data["weight"] == 70.2
    assert data["medical_histories"] == ["高血压", "糖尿病"]
    assert data["allergies"]


@pytest.mark.asyncio
async def test_family_v2_list_returns_required_fields(client: AsyncClient, auth_headers):
    """列表接口必须返回 birthday + gender + relationship_type（供前端字徽 + 年龄计算）"""
    await client.post("/api/family/members", json={
        "relationship_type": "妈妈",
        "name": "我妈",
        "nickname": "我妈",
        "gender": "female",
        "birthday": "1968-06-15",
    }, headers=auth_headers)

    resp = await client.get("/api/family/members", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    # 至少包含本人 + 妈妈
    items = data["items"]
    assert len(items) >= 1
    mama = next((m for m in items if m["relationship_type"] == "妈妈"), None)
    assert mama is not None, f"列表中应找到「妈妈」: {items}"
    assert mama["birthday"] == "1968-06-15"
    assert mama["gender"] == "female"
    assert mama["nickname"] == "我妈"


@pytest.mark.asyncio
async def test_family_v2_birthday_iso_format(client: AsyncClient, auth_headers):
    """出生日期保持 ISO YYYY-MM-DD 格式（供前端 calcAge 函数解析）"""
    resp = await client.post("/api/family/members", json={
        "relationship_type": "儿子",
        "name": "小儿子",
        "nickname": "小儿子",
        "gender": "male",
        "birthday": "2015-03-08",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # 后端返回 birthday 必须是字符串/ISO 日期格式
    bd = data.get("birthday")
    assert bd is not None
    assert str(bd).startswith("2015-03-08")


@pytest.mark.asyncio
async def test_family_v2_missing_relation_rejects(client: AsyncClient, auth_headers):
    """缺关系字段时拒绝"""
    resp = await client.post("/api/family/members", json={
        "name": "无关系",
        "nickname": "无关系",
        "gender": "male",
        "birthday": "1990-01-01",
    }, headers=auth_headers)
    # FastAPI 默认 422，本期不修后端，只要拒绝即可
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_family_v2_health_profile_birthday_provided(client: AsyncClient, auth_headers):
    """本人健康档案接口可返回 birthday（供前端拦截判断本人档案是否完善）"""
    # 先创建/更新本人档案
    await client.post("/api/health/profile", json={
        "name": "本人",
        "gender": "male",
        "birthday": "1990-06-15",
        "height": 175,
        "weight": 70,
    }, headers=auth_headers)
    resp = await client.get("/api/health/profile", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # 后端字段名取决于 schema，至少要含 birthday
    assert "birthday" in data
    bd = data.get("birthday")
    assert bd and str(bd).startswith("1990-06-15")
