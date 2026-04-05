from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection


async def _sync_ai_model_configs(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "ai_model_configs" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("ai_model_configs")}

    columns = await conn.run_sync(_load)
    if columns is None:
        return
    if "max_tokens" not in columns:
        await conn.execute(text("ALTER TABLE ai_model_configs ADD COLUMN max_tokens INT DEFAULT 4096"))
    if "temperature" not in columns:
        await conn.execute(text("ALTER TABLE ai_model_configs ADD COLUMN temperature FLOAT DEFAULT 0.7"))
    if "template_id" not in columns:
        await conn.execute(text(
            "ALTER TABLE ai_model_configs ADD COLUMN template_id INT NULL, "
            "ADD CONSTRAINT fk_ai_config_template FOREIGN KEY (template_id) REFERENCES ai_model_templates(id)"
        ))
    if "template_synced_at" not in columns:
        await conn.execute(text("ALTER TABLE ai_model_configs ADD COLUMN template_synced_at DATETIME NULL"))


async def sync_register_schema(conn: AsyncConnection) -> None:
    def load_user_schema(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "users" not in tables:
            return set(), set(), set()
        columns = {column["name"] for column in inspector.get_columns("users")}
        indexes = {index["name"] for index in inspector.get_indexes("users")}
        unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("users")
            if constraint.get("name")
        }
        return columns, indexes, unique_constraints

    await _sync_ai_model_configs(conn)

    columns, indexes, unique_constraints = await conn.run_sync(load_user_schema)

    if "wechat_openid" not in columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN wechat_openid VARCHAR(100) NULL"))
    if "apple_id" not in columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN apple_id VARCHAR(100) NULL"))
    if "member_card_no" not in columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN member_card_no VARCHAR(50) NULL"))

    unique_names = indexes | unique_constraints
    if "uq_users_wechat_openid" not in unique_names:
        await conn.execute(text("CREATE UNIQUE INDEX uq_users_wechat_openid ON users (wechat_openid)"))
    if "uq_users_apple_id" not in unique_names:
        await conn.execute(text("CREATE UNIQUE INDEX uq_users_apple_id ON users (apple_id)"))
    if "uq_users_member_card_no" not in unique_names:
        await conn.execute(text("CREATE UNIQUE INDEX uq_users_member_card_no ON users (member_card_no)"))
    if "ix_users_member_card_no" not in indexes:
        await conn.execute(text("CREATE INDEX ix_users_member_card_no ON users (member_card_no)"))
