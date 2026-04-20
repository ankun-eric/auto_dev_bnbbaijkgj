"""Bug #6 修复：全量刷新会员码脚本。

【运行注意事项】
- 请在凌晨低峰期执行。
- 脚本启动时会先执行整表备份（users → users_backup_YYYYMMDD），
  失败则终止，**不**对 users 做任何修改。
- 会将旧 member_card_no 值写入 member_card_no_old 字段用于应急回滚；
  按要求 30 天后再清理 member_card_no_old，本次不清理。
- 新会员码字符集：23456789ABCDEFGHJKLMNPQRSTUVWXYZ（32 位，去掉 0/O/1/I/L）；
  长度 6；冲突重试上限 10 次。
- 老用户**统一全量**重新生成（不加公告/弹窗）。

用法：
    cd backend
    python -m scripts.reissue_member_codes            # 正式执行
    python -m scripts.reissue_member_codes --dry-run  # 仅打印不写入
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text

from app.core.database import async_session, engine
from app.models.models import User
from app.services.member_code import (
    MEMBER_CODE_MAX_RETRIES,
    generate_member_code,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

USERS_TABLE = "users"


async def backup_users_table(dry_run: bool) -> str:
    """整表备份：CREATE TABLE users_backup_YYYYMMDD AS SELECT * FROM users"""
    today = datetime.utcnow().strftime("%Y%m%d")
    backup_name = f"{USERS_TABLE}_backup_{today}"
    sql = f"CREATE TABLE {backup_name} AS SELECT * FROM {USERS_TABLE}"
    if dry_run:
        logger.info("[dry-run] 备份语句: %s", sql)
        return backup_name

    async with engine.begin() as conn:
        exists_rs = await conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = :name"
            ),
            {"name": backup_name},
        )
        exists = int(exists_rs.scalar() or 0) > 0
        if exists:
            logger.warning("备份表 %s 已存在，跳过备份（通常说明今日已刷码过）", backup_name)
            return backup_name
        await conn.execute(text(sql))
    logger.info("整表备份完成: %s", backup_name)
    return backup_name


async def reissue_all(dry_run: bool) -> dict:
    total = 0
    success = 0
    failed = 0
    skipped = 0
    failed_user_ids: list[int] = []

    async with async_session() as session:
        users_rs = await session.execute(select(User))
        users = users_rs.scalars().all()
        total = len(users)
        logger.info("共待处理 %d 个用户", total)

        used_codes: set[str] = set()
        db_taken_rs = await session.execute(
            select(User.member_card_no).where(User.member_card_no.is_not(None))
        )
        for row in db_taken_rs.scalars().all():
            if row:
                used_codes.add(str(row).upper())

        for user in users:
            old_code = user.member_card_no
            new_code = None
            for _ in range(MEMBER_CODE_MAX_RETRIES):
                candidate = generate_member_code()
                if candidate in used_codes:
                    continue
                new_code = candidate
                break

            if new_code is None:
                failed += 1
                failed_user_ids.append(user.id)
                logger.error(
                    "user_id=%s 在 %d 次重试内仍冲突，跳过（保留原码 %s）",
                    user.id,
                    MEMBER_CODE_MAX_RETRIES,
                    old_code,
                )
                continue

            if old_code and str(old_code).upper() == new_code:
                skipped += 1
                continue

            if dry_run:
                logger.info(
                    "[dry-run] user_id=%s  %s -> %s",
                    user.id,
                    old_code,
                    new_code,
                )
            else:
                if old_code:
                    user.member_card_no_old = str(old_code)
                user.member_card_no = new_code
                if old_code:
                    used_codes.discard(str(old_code).upper())
                used_codes.add(new_code)

            success += 1

        if not dry_run:
            await session.commit()

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "skipped_same": skipped,
        "failed_user_ids": failed_user_ids,
    }


async def main_async(dry_run: bool) -> None:
    logger.info("=== 刷码开始 (dry_run=%s) ===", dry_run)
    backup_name = await backup_users_table(dry_run=dry_run)
    logger.info("备份表: %s", backup_name)

    stats = await reissue_all(dry_run=dry_run)
    logger.info("=== 刷码完成 ===")
    logger.info(
        "总数=%d 成功=%d 失败=%d 同码跳过=%d",
        stats["total"],
        stats["success"],
        stats["failed"],
        stats["skipped_same"],
    )
    if stats["failed_user_ids"]:
        logger.warning(
            "失败 user_id 列表 (前 50): %s",
            stats["failed_user_ids"][:50],
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="全量刷新会员码")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印不写入（也不执行整表备份的 DDL）",
    )
    args = parser.parse_args()
    asyncio.run(main_async(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
