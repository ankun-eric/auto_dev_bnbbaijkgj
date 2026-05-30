"""[BUG_FIX_AI_HOME_REPORT_INTERPRET_20260517 · Bug #2 修 B / §六]
家庭成员 ``is_self`` 一次性回填迁移：为每个 ``users`` 表中尚无 ``is_self=True``
``FamilyMember`` 记录的用户补建一条"本人"档案。

幂等：使用 ``NOT EXISTS`` 防重；可在每次启动时安全执行。
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.database import async_session

logger = logging.getLogger(__name__)


async def migrate_family_self() -> None:
    """补建缺失的 is_self FamilyMember 记录。"""
    try:
        async with async_session() as db:
            # 1) 先选出需要回填的用户清单（小批，避免长事务）
            # [BUG_FIX-FAMILY-NICKNAME-DEFAULT-20260530] 同步取 phone，用于兜底姓名生成
            rows = (
                await db.execute(
                    text(
                        """
                        SELECT u.id AS uid, u.nickname AS nickname, u.phone AS phone
                        FROM users u
                        WHERE NOT EXISTS (
                            SELECT 1 FROM family_members fm
                            WHERE fm.user_id = u.id AND fm.is_self = 1
                        )
                        """
                    )
                )
            ).fetchall()

            if not rows:
                logger.info("[migrate] family_self_backfill: 0 行待回填")
                return

            inserted = 0
            for r in rows:
                uid = r[0]
                raw_nick = (r[1] or "").strip() if r[1] is not None else ""
                phone = (r[2] or "").strip() if r[2] is not None else ""
                # [BUG_FIX-FAMILY-NICKNAME-DEFAULT-20260530] 统一兜底规则：
                # 1) 先用 users.nickname；2) 否则用「用户{后4位}」；3) 兜底「用户{uid}」
                if raw_nick:
                    nickname = raw_nick
                elif phone and len(phone) >= 4:
                    nickname = f"用户{phone[-4:]}"
                else:
                    nickname = f"用户{uid}"
                try:
                    await db.execute(
                        text(
                            """
                            INSERT INTO family_members
                                (user_id, relationship_type, nickname,
                                 is_self, status, created_at)
                            VALUES
                                (:uid, 'self', :nick, 1, 'active', NOW())
                            """
                        ),
                        {"uid": uid, "nick": nickname[:100]},
                    )
                    inserted += 1
                except Exception as e:
                    logger.warning(
                        "[migrate] family_self_backfill: uid=%s insert failed err=%s",
                        uid,
                        e,
                    )

            try:
                await db.commit()
            except Exception as e:
                logger.warning(
                    "[migrate] family_self_backfill: commit failed err=%s", e
                )
                try:
                    await db.rollback()
                except Exception:
                    pass
            logger.info(
                "[migrate] family_self_backfill: 回填完成 inserted=%d / total=%d",
                inserted,
                len(rows),
            )
    except Exception as e:
        logger.error("[migrate] family_self_backfill: 异常（不影响启动）: %s", e)
