"""
迁移脚本：健康自查AI增强功能 - 数据库变更

变更内容：
1. health_profiles 表：移除 user_id 的 unique 约束，添加 family_member_id 外键、medical_histories、allergies 字段
2. family_members 表：添加 birthday、gender、height、weight、medical_histories、allergies 字段
3. chat_sessions 表：添加 symptom_info 字段
"""
import asyncio
import os

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "mysql+aiomysql://root:password@localhost:3306/bini_health"
)


async def migrate():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:

        # 1. health_profiles 表变更
        print(">>> 处理 health_profiles 表...")

        # 尝试删除 user_id 上的 unique 索引（不同 MySQL 版本约束名可能不同）
        for index_name in ("ix_health_profiles_user_id", "uq_health_profiles_user_id", "health_profiles_user_id_key"):
            try:
                await conn.execute(text(f"ALTER TABLE health_profiles DROP INDEX `{index_name}`"))
                print(f"  已删除索引 {index_name}")
            except Exception:
                pass

        # 添加 family_member_id 字段
        try:
            await conn.execute(text(
                "ALTER TABLE health_profiles ADD COLUMN family_member_id INT NULL"
            ))
            print("  已添加字段 family_member_id")
        except Exception as e:
            print(f"  family_member_id 已存在或错误: {e}")

        # 添加外键约束
        try:
            await conn.execute(text(
                "ALTER TABLE health_profiles ADD CONSTRAINT fk_hp_family_member "
                "FOREIGN KEY (family_member_id) REFERENCES family_members(id) ON DELETE SET NULL"
            ))
            print("  已添加外键 fk_hp_family_member")
        except Exception as e:
            print(f"  外键已存在或错误: {e}")

        # 为 user_id 补充普通索引（如果原来只有 unique，删除后需要重新建索引）
        try:
            await conn.execute(text(
                "ALTER TABLE health_profiles ADD INDEX ix_health_profiles_user_id (user_id)"
            ))
            print("  已添加普通索引 ix_health_profiles_user_id")
        except Exception as e:
            print(f"  索引已存在或错误: {e}")

        # 添加 medical_histories 和 allergies 字段
        for col_sql, col_name in [
            ("ALTER TABLE health_profiles ADD COLUMN medical_histories JSON NULL", "medical_histories"),
            ("ALTER TABLE health_profiles ADD COLUMN allergies JSON NULL", "allergies"),
        ]:
            try:
                await conn.execute(text(col_sql))
                print(f"  已添加字段 {col_name}")
            except Exception as e:
                print(f"  {col_name} 已存在或错误: {e}")

        # 2. family_members 表变更
        print(">>> 处理 family_members 表...")
        for col_sql, col_name in [
            ("ALTER TABLE family_members ADD COLUMN birthday DATE NULL", "birthday"),
            ("ALTER TABLE family_members ADD COLUMN gender VARCHAR(10) NULL", "gender"),
            ("ALTER TABLE family_members ADD COLUMN height FLOAT NULL", "height"),
            ("ALTER TABLE family_members ADD COLUMN weight FLOAT NULL", "weight"),
            ("ALTER TABLE family_members ADD COLUMN medical_histories JSON NULL", "medical_histories"),
            ("ALTER TABLE family_members ADD COLUMN allergies JSON NULL", "allergies"),
        ]:
            try:
                await conn.execute(text(col_sql))
                print(f"  已添加字段 {col_name}")
            except Exception as e:
                print(f"  {col_name} 已存在或错误: {e}")

        # 3. chat_sessions 表变更
        print(">>> 处理 chat_sessions 表...")
        try:
            await conn.execute(text(
                "ALTER TABLE chat_sessions ADD COLUMN symptom_info JSON NULL"
            ))
            print("  已添加字段 symptom_info")
        except Exception as e:
            print(f"  symptom_info 已存在或错误: {e}")

        print("\n迁移完成!")


if __name__ == "__main__":
    asyncio.run(migrate())
