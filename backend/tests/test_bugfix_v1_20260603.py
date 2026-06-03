"""[BUGFIX V1 2026-06-03] 5 项修复回归测试

覆盖:
- 旧 1: 新建家人成员时 sub_status 不再为 NULL,显式落库
- 旧 2: schema_sync.py 2.4 任务回扫语句不再引用不存在的列 (使用 mg.cancelled_at)
- 新 1+2: 前端 UI 改动,本文件不覆盖(UI 类回归通过 lint + 构建保证)
"""
from __future__ import annotations

import re

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import FamilyMember, User
from tests.conftest import test_session


async def _register(client: AsyncClient, phone: str, nickname: str) -> tuple[int, dict]:
    await client.post("/api/auth/register", json={
        "phone": phone, "password": "pwd123456", "nickname": nickname,
    })
    res = await client.post("/api/auth/login", json={
        "phone": phone, "password": "pwd123456",
    })
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Client-Type": "h5-user"}
    async with test_session() as s:
        u = (await s.execute(select(User).where(User.phone == phone))).scalar_one()
        return u.id, headers


@pytest.mark.asyncio
async def test_bugfix_old1_new_family_member_sub_status_not_null_no_member_user(
    client: AsyncClient,
):
    """[BUGFIX 旧 1] 通过 /api/family/members 新建一个纯档案家人(无 member_user_id),
    sub_status 必须显式落库为 'not_applied',status 必须为 'unbound'。
    """
    uid, headers = await _register(client, "13690000701", "BFOLD1主账号")

    res = await client.post(
        "/api/family/members",
        headers=headers,
        json={
            "nickname": "纯档案家人A",
            "relationship_type": "父亲",
        },
    )
    assert res.status_code in (200, 201), f"新建家人失败: {res.status_code} {res.text}"

    async with test_session() as s:
        rows = (
            await s.execute(
                select(FamilyMember).where(
                    FamilyMember.user_id == uid,
                    FamilyMember.is_self.is_(False),
                    FamilyMember.nickname == "纯档案家人A",
                )
            )
        ).scalars().all()
        assert len(rows) == 1, f"应只有一行新建成员,实际 {len(rows)} 行"
        m = rows[0]
        assert m.sub_status is not None, "sub_status 不应为 NULL(BUGFIX 旧 1 回归)"
        assert m.sub_status == "not_applied", (
            f"纯档案家人初始 sub_status 应为 'not_applied',实际 {m.sub_status!r}"
        )
        assert m.status == "unbound", (
            f"纯档案家人初始 status 应为 'unbound',实际 {m.status!r}"
        )


@pytest.mark.asyncio
async def test_bugfix_old1_new_family_member_sub_status_not_null_with_member_user(
    client: AsyncClient,
):
    """[BUGFIX 旧 1] 新建一个直接关联到已存在用户的家人,
    sub_status 必须显式落库为 'bound',status 必须为 'bound'。
    """
    uid_owner, headers_owner = await _register(client, "13690000702", "BFOLD2主账号")
    uid_target, _ = await _register(client, "13690000703", "BFOLD2目标")

    res = await client.post(
        "/api/family/members",
        headers=headers_owner,
        json={
            "nickname": "已绑定家人B",
            "relationship_type": "妻子",
            "member_user_id": uid_target,
        },
    )
    assert res.status_code in (200, 201), f"新建家人失败: {res.status_code} {res.text}"

    async with test_session() as s:
        rows = (
            await s.execute(
                select(FamilyMember).where(
                    FamilyMember.user_id == uid_owner,
                    FamilyMember.is_self.is_(False),
                    FamilyMember.nickname == "已绑定家人B",
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        m = rows[0]
        assert m.sub_status == "bound", (
            f"已绑定家人初始 sub_status 应为 'bound',实际 {m.sub_status!r}"
        )
        assert m.status == "bound", (
            f"已绑定家人初始 status 应为 'bound',实际 {m.status!r}"
        )


def test_bugfix_old2_schema_sync_no_invalid_upd_column():
    """[BUGFIX 旧 2] schema_sync.py 中调度任务 2.4 回扫 SQL 不再引用不存在的 mg.updated_at,
    必须改为 family_management 实际存在的 cancelled_at / created_at。

    仅扫描非注释行,避免修复说明中提到的字段名被误判。
    """
    import pathlib
    here = pathlib.Path(__file__).resolve().parent
    schema_sync = here.parent / "app" / "services" / "schema_sync.py"
    assert schema_sync.exists(), f"未找到 schema_sync.py: {schema_sync}"
    content = schema_sync.read_text(encoding="utf-8")

    invalid_lines = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        stripped = line.lstrip()
        # 跳过 Python 行内注释
        if stripped.startswith("#"):
            continue
        if "mg.updated_at" in line:
            # 进一步过滤:只判定 SQL 字符串中的实际使用(出现在 text("...") 或 SQL 模板字符串)
            # 简化规则:只要不是 Python 注释行,且包含 mg.updated_at,就认为是实际 SQL 引用
            invalid_lines.append(f"line {lineno}: {line.strip()}")

    assert not invalid_lines, (
        "schema_sync.py 仍然在非注释代码中引用了不存在的 mg.updated_at 列,"
        "请改用 mg.cancelled_at / mg.created_at:\n  " + "\n  ".join(invalid_lines)
    )

    # 必须包含修复后的引用
    assert "mg.cancelled_at" in content, (
        "schema_sync.py 应改为引用 family_management 实际存在的 cancelled_at 列"
    )
