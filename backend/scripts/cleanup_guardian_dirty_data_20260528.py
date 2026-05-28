"""[BUGFIX-MY-GUARDIAN-CARD-2-20260528] 一次性脏数据清理脚本

清理范围（A1~A4 四类）：
- A1：family_management.invitation_id 字段悬空（如表中有该字段）→ 置 NULL
- A2：family_management.managed_member_id 指向已删除/不存在的 family_members → 删除该 mgmt
- A3：family_management.manager_user_id 指向已不存在的 users → 删除该 mgmt
- A4：同一 (manager_user_id, managed_member_id) 多条重复 → 仅保留最新一条

执行方式（在 backend/ 目录或容器内）：
    python scripts/cleanup_guardian_dirty_data_20260528.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# 兼容直接 python 调用
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from app.core.database import async_session as async_session_maker  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run() -> None:
    async with async_session_maker() as s:
        # A1：检查 family_management 是否含 invitation_id 列；如有则清理悬空引用
        try:
            col_check = await s.execute(text(
                "SELECT COUNT(*) FROM information_schema.COLUMNS "
                "WHERE TABLE_NAME = 'family_management' AND COLUMN_NAME = 'invitation_id'"
            ))
            has_col = int(col_check.scalar() or 0) > 0
            if has_col:
                a1 = await s.execute(text(
                    "UPDATE family_management "
                    "SET invitation_id = NULL "
                    "WHERE invitation_id IS NOT NULL "
                    "AND invitation_id NOT IN (SELECT id FROM family_invitations)"
                ))
                logger.info("A1 清理悬空 invitation_id 引用，受影响行数：%s", a1.rowcount)
            else:
                logger.info("A1 跳过：family_management 表无 invitation_id 列")
        except Exception as e:
            logger.warning("A1 清理失败：%s", e)

        # A2：family_management.managed_member_id 指向不存在的 family_members → 删除
        try:
            a2 = await s.execute(text(
                "DELETE FROM family_management "
                "WHERE managed_member_id IS NOT NULL "
                "AND managed_member_id NOT IN (SELECT id FROM family_members)"
            ))
            logger.info("A2 清理悬空 managed_member_id 的 mgmt，受影响行数：%s", a2.rowcount)
        except Exception as e:
            logger.warning("A2 清理失败：%s", e)

        # A3：family_management.manager_user_id 指向已不存在 users → 删除
        try:
            a3 = await s.execute(text(
                "DELETE FROM family_management "
                "WHERE manager_user_id NOT IN (SELECT id FROM users)"
            ))
            logger.info("A3 清理 manager_user_id 已注销的 mgmt，受影响行数：%s", a3.rowcount)
        except Exception as e:
            logger.warning("A3 清理失败：%s", e)

        # A4：同一 (manager_user_id, managed_member_id) 多条 → 仅保留最新一条（id 最大）
        try:
            a4 = await s.execute(text(
                "DELETE m1 FROM family_management m1 "
                "INNER JOIN family_management m2 "
                "ON m1.manager_user_id = m2.manager_user_id "
                "AND m1.managed_member_id = m2.managed_member_id "
                "AND m1.managed_member_id IS NOT NULL "
                "AND m1.id < m2.id"
            ))
            logger.info("A4 清理 (manager_user_id, managed_member_id) 重复 mgmt，受影响行数：%s", a4.rowcount)
        except Exception as e:
            logger.warning("A4 清理失败：%s", e)

        await s.commit()
        logger.info("脏数据清理完成 ✅")


if __name__ == "__main__":
    asyncio.run(run())
