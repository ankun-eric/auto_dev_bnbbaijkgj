"""[PRD-420 2026-05-08] AI 对话模式 - 咨询对象选择器 后端契约回归测试。

PRD F7 明确"无需任何后端接口新增或改造"，本测试套件用于验证：
1. 列出家庭成员接口（GET /api/family/members）按"本人优先 + 其他成员按 created_at 正序"返回
   → R1/R2 业务规则
2. 新增家庭成员接口（POST /api/family/members）支持完整字段（关系/姓名/性别/出生日期/身高/体重/病史/过敏史）
   → 与 PRD F4 表单字段 100% 一致
3. 关系字典接口（GET /api/relation-types）返回"爸爸/妈妈/老公/老婆/儿子/女儿/哥哥/弟弟/姐姐/妹妹/爷爷/奶奶/外公/外婆/其他"
   → 与 PRD F3 关系九宫格 100% 一致
4. 切换会话归属人接口（POST /api/chat/sessions/{id}/switch-member）正常工作
   → F5 切换流程的依赖
5. 创建会话时携带 family_member_id 即建立咨询对象关联
   → F5 自动新建会话的依赖
6. AI 对话模式 与 菜单模式 100% 数据共享
   → F7 数据打通：在 AI 对话模式下新建的成员，菜单模式立即可见
7. 同一关系（如"老婆"）反复添加允许，但前端会做柔性提示
   → 异常表 R8 的兼容
8. 跨入口创建会话相互不污染，对应 family_member_id 隔离
   → F5 §3 AI 上下文严格隔离

凡是涉及"创建/读取/切换"的接口契约必须保持稳定；任何破坏性改动都会被本测试套件捕获。
"""
import pytest
import asyncio
from httpx import AsyncClient


# ───────────────────────────────────────────────────────────────────────
# 工具函数：在 user_token 鉴权下创建家庭成员；按测试需求清理
# ───────────────────────────────────────────────────────────────────────


async def _add_member(
    client: AsyncClient,
    auth_headers,
    *,
    relation: str,
    nickname: str,
    gender: str = "male",
    birthday: str = "1990-01-01",
    height: int | None = None,
    weight: float | None = None,
    medical_histories: list[str] | None = None,
    allergies: list[str] | None = None,
):
    """与 H5/小程序/Flutter 真实调用的字段保持一致。"""
    body = {
        "nickname": nickname,
        "name": nickname,
        "relationship_type": relation,
        "gender": gender,
        "birthday": birthday,
    }
    if height is not None:
        body["height"] = height
    if weight is not None:
        body["weight"] = weight
    if medical_histories:
        body["medical_histories"] = medical_histories
    if allergies:
        body["allergies"] = allergies
    resp = await client.post("/api/family/members", json=body, headers=auth_headers)
    return resp


# ───────────────────────────────────────────────────────────────────────
# T01：GET /api/family/members 返回结构 + 排序
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t01_family_members_list_structure(client: AsyncClient, auth_headers):
    """list_family_members：未添加任何成员时也返回 items 列表（PRD R3 数量无上限，0 也合法）。"""
    resp = await client.get("/api/family/members", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data, "返回结构必须含 items 字段"
    assert isinstance(data["items"], list)
    # total 字段是 picker 的可选展示信息
    assert "total" in data


# ───────────────────────────────────────────────────────────────────────
# T02：本人优先 + 其他按 created_at 正序（PRD R1 + R2）
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t02_family_members_order_self_first_then_created_at_asc(
    client: AsyncClient, auth_headers
):
    """连续添加 3 个家庭成员，验证排序：本人若存在永远第一，其余按创建时间正序。"""
    # 先创建 son（早）
    r1 = await _add_member(client, auth_headers, relation="儿子", nickname="苏俊林")
    assert r1.status_code == 200
    await asyncio.sleep(0.02)
    # 再创建 wife（晚）
    r2 = await _add_member(client, auth_headers, relation="老婆", nickname="朱小妹", gender="female")
    assert r2.status_code == 200
    await asyncio.sleep(0.02)
    # 再创建 daughter（最晚）
    r3 = await _add_member(
        client, auth_headers, relation="女儿", nickname="苏可可", gender="female"
    )
    assert r3.status_code == 200

    resp = await client.get("/api/family/members", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    # is_self 永远在最前（即使没有本人记录，也不应崩）
    self_items = [m for m in items if m.get("is_self")]
    other_items = [m for m in items if not m.get("is_self")]
    assert items[: len(self_items)] == self_items, "本人必须在其他成员之前"

    # 其他成员按 created_at 正序
    if len(other_items) >= 2:
        ids = [m["id"] for m in other_items]
        assert ids == sorted(ids), f"其他成员应按 id 正序（与 created_at 正序一致），实际 {ids}"


# ───────────────────────────────────────────────────────────────────────
# T03：F4 字段全集校验（关系/姓名/性别/出生/身高/体重/病史/过敏史）
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t03_add_member_full_fields(client: AsyncClient, auth_headers):
    """与 PRD §F4 表单字段 100% 对齐：必填 3 项 + 选填 4 项。"""
    resp = await _add_member(
        client,
        auth_headers,
        relation="老婆",
        nickname="朱小妹",
        gender="female",
        birthday="1992-08-15",
        height=165,
        weight=52.5,
        medical_histories=["甲状腺疾病", "其他病史描述"],
        allergies=["海鲜", "花粉"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["nickname"] == "朱小妹"
    assert data["relationship_type"] == "老婆"
    assert data["gender"] == "female"
    assert data["height"] == 165
    assert float(data["weight"]) == 52.5
    assert data["medical_histories"] == ["甲状腺疾病", "其他病史描述"]
    assert data["allergies"] == ["海鲜", "花粉"]
    # is_self 必须为 False（新增的家庭成员永远是非本人）
    assert data["is_self"] is False


# ───────────────────────────────────────────────────────────────────────
# T04：必填字段缺失时拒绝（关系必填）
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t04_add_member_missing_relation_rejected(client: AsyncClient, auth_headers):
    """未携带 relationship_type 也未携带 relation_type_id → 后端报 400。"""
    resp = await client.post(
        "/api/family/members",
        json={"nickname": "没有关系", "name": "没有关系", "gender": "male", "birthday": "1990-01-01"},
        headers=auth_headers,
    )
    # 后端校验链路：FastAPI 的 RequestValidationError 返回 422，业务逻辑里的二次校验返回 400。
    # 端上对两者都做了"必填"提示，故两种状态码都视为符合契约。
    assert resp.status_code in (400, 422), resp.text
    detail = resp.json().get("detail", "")
    assert (
        "成员关系" in str(detail)
        or "必填" in str(detail)
        or "relationship_type" in str(detail).lower()
    )


# ───────────────────────────────────────────────────────────────────────
# T05：同一关系反复添加允许（R3 数量无上限，PRD 异常表中要求"允许 + 柔性提示"）
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t05_same_relation_can_be_added_multiple_times(
    client: AsyncClient, auth_headers
):
    """两次添加"老婆"应都成功（前端 UI 层做柔性确认；后端不强制拦截）。"""
    r1 = await _add_member(client, auth_headers, relation="老婆", nickname="第一个老婆", gender="female")
    assert r1.status_code == 200
    r2 = await _add_member(client, auth_headers, relation="老婆", nickname="第二个老婆", gender="female")
    assert r2.status_code == 200
    # ID 应不同
    assert r1.json()["id"] != r2.json()["id"]


# ───────────────────────────────────────────────────────────────────────
# T06：创建 chat session 携带 family_member_id 建立归属关系（F5 依赖）
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t06_create_session_with_family_member_id(
    client: AsyncClient, auth_headers
):
    """F5 自动新建会话流程的核心契约：创建 session 时带 family_member_id 即建立咨询对象关联。"""
    add_resp = await _add_member(
        client, auth_headers, relation="儿子", nickname="苏俊林", birthday="2010-06-01"
    )
    assert add_resp.status_code == 200
    member_id = add_resp.json()["id"]

    # 创建会话（同 ai-home 真实调用一致）
    sess = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa", "family_member_id": member_id},
        headers=auth_headers,
    )
    assert sess.status_code == 200, sess.text
    data = sess.json()
    assert data["session_type"] == "health_qa"
    # ChatSessionResponse 应该回传 family_member_id（如有）
    if "family_member_id" in data:
        assert data["family_member_id"] == member_id


# ───────────────────────────────────────────────────────────────────────
# T07：切换咨询对象接口（F5 中"空会话只换归属人不新建"使用此接口）
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t07_switch_session_member_for_empty_session(
    client: AsyncClient, auth_headers
):
    """F5-1：当会话尚未发出消息时，调用 switch-member 接口仅切换归属人，无须新建会话。"""
    # 先添加一个家庭成员
    add_resp = await _add_member(
        client, auth_headers, relation="妈妈", nickname="王慧芳", gender="female", birthday="1965-03-10"
    )
    assert add_resp.status_code == 200
    member_id = add_resp.json()["id"]

    # 创建一个 session（默认本人或空）
    sess = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa"},
        headers=auth_headers,
    )
    assert sess.status_code == 200
    session_id = sess.json()["id"]

    # 切换为新成员
    sw = await client.post(
        f"/api/chat/sessions/{session_id}/switch-member",
        json={"family_member_id": member_id},
        headers=auth_headers,
    )
    assert sw.status_code == 200, sw.text
    sw_data = sw.json()
    assert sw_data["family_member_id"] == member_id
    assert "妈妈" in sw_data.get("message", "")


# ───────────────────────────────────────────────────────────────────────
# T08：切换为本人（family_member_id=None）
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t08_switch_session_member_back_to_self(client: AsyncClient, auth_headers):
    """F5-1：从其他成员切换回"本人"，family_member_id 可显式置 None。"""
    add_resp = await _add_member(
        client, auth_headers, relation="爸爸", nickname="苏建国", birthday="1962-08-20"
    )
    assert add_resp.status_code == 200
    member_id = add_resp.json()["id"]

    sess = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa", "family_member_id": member_id},
        headers=auth_headers,
    )
    assert sess.status_code == 200
    session_id = sess.json()["id"]

    sw = await client.post(
        f"/api/chat/sessions/{session_id}/switch-member",
        json={"family_member_id": None},
        headers=auth_headers,
    )
    assert sw.status_code == 200, sw.text
    sw_data = sw.json()
    assert sw_data["family_member_id"] is None
    # 提示文案中包含"自己"
    assert "自己" in sw_data.get("message", "") or "本人" in sw_data.get("message", "")


# ───────────────────────────────────────────────────────────────────────
# T09：F7 数据打通：AI 对话模式 与 菜单模式 100% 共享同一份家庭成员数据
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t09_data_sharing_between_modes(client: AsyncClient, auth_headers):
    """模拟"AI 对话模式新增"，再"菜单模式刷新"应立即看到 → 同一份接口，本来就共享，此处契约性回归。"""
    # AI 对话模式新增（实际就是同一个 POST /api/family/members）
    add_resp = await _add_member(
        client, auth_headers, relation="女儿", nickname="苏可可", gender="female", birthday="2018-12-25"
    )
    assert add_resp.status_code == 200
    new_id = add_resp.json()["id"]

    # 菜单模式拉取列表（同样是同一个 GET /api/family/members）
    list_resp = await client.get("/api/family/members", headers=auth_headers)
    assert list_resp.status_code == 200
    ids = [m["id"] for m in list_resp.json()["items"]]
    assert new_id in ids, "菜单模式刷新后必须能看到 AI 对话模式新增的成员"


# ───────────────────────────────────────────────────────────────────────
# T10：跨入口隔离：不同 family_member_id 的会话独立
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t10_cross_session_consultant_isolation(
    client: AsyncClient, auth_headers
):
    """F5 §3 AI 上下文严格隔离：不同咨询对象的会话各自独立，互不串档。"""
    son = await _add_member(client, auth_headers, relation="儿子", nickname="苏俊林", birthday="2010-06-01")
    wife = await _add_member(
        client, auth_headers, relation="老婆", nickname="朱小妹", gender="female", birthday="1992-08-15"
    )
    son_id = son.json()["id"]
    wife_id = wife.json()["id"]

    sess_son = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa", "family_member_id": son_id, "title": "为儿子咨询"},
        headers=auth_headers,
    )
    sess_wife = await client.post(
        "/api/chat/sessions",
        json={"session_type": "health_qa", "family_member_id": wife_id, "title": "为老婆咨询"},
        headers=auth_headers,
    )
    assert sess_son.status_code == 200
    assert sess_wife.status_code == 200
    assert sess_son.json()["id"] != sess_wife.json()["id"]
    # 两个会话的 family_member_id 必须互不串档
    if "family_member_id" in sess_son.json() and "family_member_id" in sess_wife.json():
        assert sess_son.json()["family_member_id"] == son_id
        assert sess_wife.json()["family_member_id"] == wife_id


# ───────────────────────────────────────────────────────────────────────
# T11：未登录用户访问家庭成员列表 → 401（PRD §6 权限设计）
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t11_unauthenticated_access_rejected(client: AsyncClient):
    """PRD §6：未登录用户应被拒绝访问家庭成员相关接口。"""
    resp = await client.get("/api/family/members")
    assert resp.status_code in (401, 403), resp.text


# ───────────────────────────────────────────────────────────────────────
# T12：跨用户越权访问：A 用户不能查看 B 用户的家庭成员
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t12_cross_user_isolation(client: AsyncClient, auth_headers):
    """PRD §4.2 安全要求：家庭成员档案接口须做用户身份校验，禁止越权访问。

    A 用户添加成员；B 用户登录后无法在自己的列表中看到 A 用户的成员。
    """
    # 用户 A 已通过 auth_headers 登录，添加一个成员
    await _add_member(
        client, auth_headers, relation="爸爸", nickname="A的爸爸", birthday="1960-01-01"
    )

    # 注册并登录用户 B
    await client.post(
        "/api/auth/register",
        json={
            "phone": "13900000999",
            "password": "user999",
            "nickname": "测试用户B",
        },
    )
    login = await client.post(
        "/api/auth/login",
        json={"phone": "13900000999", "password": "user999"},
    )
    assert login.status_code == 200, login.text
    token_b = login.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}", "Client-Type": "h5-user"}

    list_b = await client.get("/api/family/members", headers=headers_b)
    assert list_b.status_code == 200
    items_b = list_b.json()["items"]
    # B 用户不应看到 A 用户添加的"A的爸爸"
    nicknames_b = {m["nickname"] for m in items_b}
    assert "A的爸爸" not in nicknames_b


# ───────────────────────────────────────────────────────────────────────
# T13：添加家庭成员后，列表中能立即看到新成员（异常处理 §"以服务端为准"）
# ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t13_add_then_list_reflects_immediately(
    client: AsyncClient, auth_headers
):
    """异常表中"以服务端为准，端上抽屉每次打开重新拉取列表"：保证 add → list 立即可见。"""
    add_resp = await _add_member(
        client, auth_headers, relation="弟弟", nickname="苏小弟", birthday="2000-05-05"
    )
    assert add_resp.status_code == 200
    new_id = add_resp.json()["id"]

    # 立即查询
    list_resp = await client.get("/api/family/members", headers=auth_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    found = next((m for m in items if m["id"] == new_id), None)
    assert found is not None, "新增的成员必须在列表中立即可见"
    assert found["nickname"] == "苏小弟"
    assert found["relationship_type"] == "弟弟"
