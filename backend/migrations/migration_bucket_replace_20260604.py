"""
Bucket 路径批量替换迁移脚本 (Python 版)
日期：2026-06-04
说明：将数据库中所有存量的旧 Bucket 名称替换为新 Bucket 名称
   旧：xiaokang-1323135906
   新：xiaokang-prod-1420478721
用法：
   方式一（推荐）：python -m migrations.migration_bucket_replace_20260604 -y
   方式二（直接执行）：python backend/migrations/migration_bucket_replace_20260604.py -y
   回滚模式：python backend/migrations/migration_bucket_replace_20260604.py --rollback
   环境变量：AUTO_CONFIRM=1 可跳过交互确认
注意：
   1. 执行前请确保已备份数据库
   2. 此脚本仅修改数据库中的 URL 文本，不涉及 COS 文件实际迁移
   3. cos_configs 表中的 bucket 字段是配置值，不会被替换
   4. 替换结果会写入 _migration_bucket_log 日志表
"""

import argparse
import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from app.core.database import async_session

OLD_BUCKET = "xiaokang-1323135906"
NEW_BUCKET = "xiaokang-prod-1420478721"

# 需要扫描的字段类型（数据库原生类型）
SCAN_DATA_TYPES = {"varchar", "char", "text", "tinytext", "mediumtext", "longtext", "json"}

# 需要跳过的表（配置表，bucket 字段是配置值而非文件 URL）
SKIP_TABLES = set()

# 需要跳过的特定字段（表.字段 格式）
SKIP_COLUMNS = {
    "cos_configs.bucket",  # 这是配置值，不应被替换
}
async def get_string_columns(db):
    """获取所有需要扫描的字符串/文本/JSON 字段（通过 INFORMATION_SCHEMA 查询）"""
    sql = text("""
        SELECT TABLE_NAME, COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND DATA_TYPE IN ('varchar', 'char', 'text', 'tinytext', 'mediumtext', 'longtext', 'json')
        ORDER BY TABLE_NAME, ORDINAL_POSITION
    """)
    result = await db.execute(sql)
    rows = result.fetchall()

    columns_to_scan = []
    for table_name, col_name in rows:
        if table_name.startswith("_migration"):
            continue
        if table_name in SKIP_TABLES:
            continue
        full_name = f"{table_name}.{col_name}"
        if full_name in SKIP_COLUMNS:
            continue
        columns_to_scan.append((table_name, col_name))

    return columns_to_scan
async def scan_existing_references(db, columns):
    """扫描当前数据库中包含旧 Bucket 的记录数"""
    print("=" * 60)
    print("第一步：扫描数据库中包含旧 Bucket 的记录")
    print(f"旧 Bucket: {OLD_BUCKET}")
    print(f"新 Bucket: {NEW_BUCKET}")
    print("=" * 60)

    total_count = 0
    affected_tables = []

    for table_name, col_name in columns:
        sql = text(
            f"SELECT COUNT(*) FROM `{table_name}` "
            f"WHERE `{col_name}` LIKE :pattern"
        )
        result = await db.execute(sql, {"pattern": f"%{OLD_BUCKET}%"})
        count = result.scalar()

        if count > 0:
            affected_tables.append((table_name, col_name, count))
            total_count += count
            print(f"  {table_name}.{col_name}: {count} 条")

    print(f"\n共发现 {total_count} 条记录涉及 {len(affected_tables)} 个字段需要替换")
    return affected_tables, total_count
async def execute_replace(db, affected_tables):
    """执行批量替换"""
    if not affected_tables:
        print("\n没有需要替换的记录，迁移结束。")
        return []

    print("\n" + "=" * 60)
    print("第二步：执行替换")
    print("=" * 60)

    log_entries = []
    total_updated = 0

    for table_name, col_name, _ in affected_tables:
        sql = text(
            f"UPDATE `{table_name}` "
            f"SET `{col_name}` = REPLACE(`{col_name}`, :old, :new) "
            f"WHERE `{col_name}` LIKE :pattern"
        )
        result = await db.execute(sql, {
            "old": OLD_BUCKET,
            "new": NEW_BUCKET,
            "pattern": f"%{OLD_BUCKET}%"
        })
        updated = result.rowcount
        total_updated += updated
        log_entries.append((table_name, col_name, updated))
        print(f"  {table_name}.{col_name}: 更新 {updated} 行")

    print(f"\n总计更新 {total_updated} 行")
    return log_entries
async def verify(db, columns):
    """验证是否还有遗漏"""
    print("\n" + "=" * 60)
    print("第三步：验证 —— 检查是否还有遗漏")
    print("=" * 60)

    remaining = 0
    for table_name, col_name in columns:
        sql = text(
            f"SELECT COUNT(*) FROM `{table_name}` "
            f"WHERE `{col_name}` LIKE :pattern"
        )
        result = await db.execute(sql, {"pattern": f"%{OLD_BUCKET}%"})
        count = result.scalar()
        if count > 0:
            print(f"  [警告] {table_name}.{col_name}: 仍有 {count} 条未替换!")
            remaining += count

    if remaining == 0:
        print("  验证通过，数据库中已无旧 Bucket 引用。")
    else:
        print(f"\n  警告：仍有 {remaining} 条记录未替换，请检查！")

    return remaining == 0
async def write_migration_log(db, log_entries):
    """将迁移结果写入数据库日志表 _migration_bucket_log"""
    for table_name, col_name, updated in log_entries:
        await db.execute(
            text(
                "INSERT INTO _migration_bucket_log (table_name, column_name, affected_rows) "
                "VALUES (:tbl, :col, :cnt)"
            ),
            {"tbl": table_name, "col": col_name, "cnt": updated},
        )
    # 日志表在 SQL 脚本中创建，这里确保已存在
    await db.execute(text(
        "CREATE TABLE IF NOT EXISTS _migration_bucket_log ("
        "  id INT AUTO_INCREMENT PRIMARY KEY,"
        "  table_name VARCHAR(128) NOT NULL,"
        "  column_name VARCHAR(128) NOT NULL,"
        "  affected_rows INT DEFAULT 0,"
        "  executed_at DATETIME DEFAULT NOW()"
        ")"
    ))


async def rollback(db, columns):
    """回滚：将新 Bucket 替换回旧 Bucket（逆向迁移）"""
    print("\n" + "=" * 60)
    print("执行回滚：将新 Bucket 替换回旧 Bucket")
    print(f"  新 -> 旧: {NEW_BUCKET} -> {OLD_BUCKET}")
    print("=" * 60)

    total_rolled_back = 0
    for table_name, col_name in columns:
        sql = text(
            f"UPDATE `{table_name}` "
            f"SET `{col_name}` = REPLACE(`{col_name}`, :new, :old) "
            f"WHERE `{col_name}` LIKE :pattern"
        )
        result = await db.execute(sql, {
            "old": OLD_BUCKET,
            "new": NEW_BUCKET,
            "pattern": f"%{NEW_BUCKET}%"
        })
        updated = result.rowcount
        if updated > 0:
            total_rolled_back += updated
            print(f"  {table_name}.{col_name}: 回滚 {updated} 行")

    print(f"\n总计回滚 {total_rolled_back} 行")
    return total_rolled_back


async def main(auto_confirm=False):
    print(f"\n{'=' * 60}")
    print(f"  Bucket 路径批量替换迁移脚本")
    print(f"  执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  数据库: bini_health")
    print(f"{'=' * 60}\n")

    async with async_session() as db:
        try:
            columns = await get_string_columns(db)
            print(f"检测到 {len(columns)} 个字符串/文本/JSON 字段需要扫描\n")

            affected, total = await scan_existing_references(db, columns)

            if total == 0:
                print("\n无需执行替换，脚本结束。")
                return

            print("\n" + "-" * 40)
            if auto_confirm:
                print("自动确认模式：跳过交互确认，直接执行替换。")
            else:
                response = input("确认执行替换？输入 yes 继续: ")
                if response.strip().lower() != "yes":
                    print("已取消。")
                    return

            log_entries = await execute_replace(db, affected)
            await write_migration_log(db, log_entries)
            await db.commit()

            success = await verify(db, columns)

            print("\n" + "=" * 60)
            if success:
                print("  迁移完成！")
            else:
                print("  迁移完成，但存在未替换的记录，请人工检查。")
            print(f"  完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)

        except Exception as e:
            await db.rollback()
            print(f"\n[错误] 迁移失败: {e}")
            raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bucket 路径批量替换迁移脚本"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        default=os.environ.get("AUTO_CONFIRM", "") == "1",
        help="跳过交互确认，直接执行替换（也可通过环境变量 AUTO_CONFIRM=1 设置）"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="回滚模式：将新 Bucket 替换回旧 Bucket"
    )
    args = parser.parse_args()

    if args.rollback:
        async def _rollback_main():
            async with async_session() as db:
                try:
                    columns = await get_string_columns(db)
                    await rollback(db, columns)
                    await db.commit()
                    print("\n回滚完成。")
                except Exception as e:
                    await db.rollback()
                    print(f"\n[错误] 回滚失败: {e}")
                    raise
        asyncio.run(_rollback_main())
    else:
        asyncio.run(main(auto_confirm=args.yes))
