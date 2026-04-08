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
    if "last_test_status" not in columns:
        await conn.execute(text("ALTER TABLE ai_model_configs ADD COLUMN last_test_status VARCHAR(20) NULL"))
    if "last_test_time" not in columns:
        await conn.execute(text("ALTER TABLE ai_model_configs ADD COLUMN last_test_time DATETIME NULL"))
    if "last_test_message" not in columns:
        await conn.execute(text("ALTER TABLE ai_model_configs ADD COLUMN last_test_message VARCHAR(500) NULL"))


async def _sync_sms_tables(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        logs_cols = None
        tpl_cols = None
        if "sms_logs" in tables:
            logs_cols = {col["name"] for col in inspector.get_columns("sms_logs")}
        if "sms_templates" in tables:
            tpl_cols = {col["name"] for col in inspector.get_columns("sms_templates")}
        return logs_cols, tpl_cols

    logs_cols, tpl_cols = await conn.run_sync(_load)

    if logs_cols is not None and "template_params" not in logs_cols:
        await conn.execute(text("ALTER TABLE sms_logs ADD COLUMN template_params VARCHAR(1000) NULL"))

    if tpl_cols is not None:
        def _check_col_type(sync_conn):
            inspector = inspect(sync_conn)
            for col in inspector.get_columns("sms_templates"):
                if col["name"] == "variables":
                    return str(col["type"])
            return ""

        col_type = await conn.run_sync(_check_col_type)
        if "TEXT" not in col_type.upper():
            await conn.execute(text("ALTER TABLE sms_templates MODIFY COLUMN variables TEXT NULL"))


async def _sync_member_levels(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "member_levels" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("member_levels")}

    columns = await conn.run_sync(_load)
    if columns is None:
        return
    if "icon" not in columns:
        await conn.execute(text("ALTER TABLE member_levels ADD COLUMN icon VARCHAR(50) NULL"))
    if "color" not in columns:
        await conn.execute(text("ALTER TABLE member_levels ADD COLUMN color VARCHAR(20) NULL"))


async def _sync_chat_session_fields(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        session_cols = None
        message_cols = None
        if "chat_sessions" in tables:
            session_cols = {col["name"] for col in inspector.get_columns("chat_sessions")}
        if "chat_messages" in tables:
            message_cols = {col["name"] for col in inspector.get_columns("chat_messages")}
        return session_cols, message_cols

    session_cols, message_cols = await conn.run_sync(_load)

    if session_cols is not None:
        if "model_name" not in session_cols:
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN model_name VARCHAR(100) NULL"))
        if "message_count" not in session_cols:
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN message_count INT DEFAULT 0"))
        if "is_pinned" not in session_cols:
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN is_pinned BOOLEAN DEFAULT FALSE"))
        if "is_deleted" not in session_cols:
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE"))
        if "share_token" not in session_cols:
            await conn.execute(text(
                "ALTER TABLE chat_sessions ADD COLUMN share_token VARCHAR(100) NULL UNIQUE"
            ))
        if "device_info" not in session_cols:
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN device_info VARCHAR(500) NULL"))
        if "ip_address" not in session_cols:
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN ip_address VARCHAR(50) NULL"))
        if "ip_location" not in session_cols:
            await conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN ip_location VARCHAR(100) NULL"))

    if message_cols is not None:
        if "response_time_ms" not in message_cols:
            await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN response_time_ms INT NULL"))
        if "prompt_tokens" not in message_cols:
            await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN prompt_tokens INT NULL"))
        if "completion_tokens" not in message_cols:
            await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN completion_tokens INT NULL"))
        if "image_urls" not in message_cols:
            await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN image_urls JSON NULL"))
        if "file_urls" not in message_cols:
            await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN file_urls JSON NULL"))


async def _sync_knowledge_tables(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        result = {}
        for tbl in [
            "knowledge_bases", "knowledge_entries", "knowledge_entry_products",
            "knowledge_search_configs", "knowledge_fallback_configs",
            "knowledge_scene_bindings", "knowledge_hit_logs",
            "knowledge_missed_questions", "knowledge_import_tasks",
            "cos_configs", "cos_files",
        ]:
            if tbl in tables:
                result[tbl] = {col["name"] for col in inspector.get_columns(tbl)}
        return result

    table_cols = await conn.run_sync(_load)

    if "knowledge_entries" in table_cols:
        cols = table_cols["knowledge_entries"]
        if "embedding_vector" not in cols:
            await conn.execute(text("ALTER TABLE knowledge_entries ADD COLUMN embedding_vector TEXT NULL"))
        if "updated_by" not in cols:
            await conn.execute(text("ALTER TABLE knowledge_entries ADD COLUMN updated_by INT NULL"))

    if "knowledge_bases" in table_cols:
        cols = table_cols["knowledge_bases"]
        if "active_entry_count" not in cols:
            await conn.execute(text("ALTER TABLE knowledge_bases ADD COLUMN active_entry_count INT DEFAULT 0"))
        if "updated_by" not in cols:
            await conn.execute(text("ALTER TABLE knowledge_bases ADD COLUMN updated_by INT NULL"))

    if "knowledge_hit_logs" in table_cols:
        cols = table_cols["knowledge_hit_logs"]
        if "session_id" not in cols:
            await conn.execute(text("ALTER TABLE knowledge_hit_logs ADD COLUMN session_id INT NULL"))
        if "message_id" not in cols:
            await conn.execute(text("ALTER TABLE knowledge_hit_logs ADD COLUMN message_id INT NULL"))


async def _sync_ai_center_tables(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        result = {}
        for tbl in ["ai_sensitive_words", "ai_prompt_configs", "ai_disclaimer_configs"]:
            if tbl in tables:
                result[tbl] = {col["name"] for col in inspector.get_columns(tbl)}
        return result

    table_cols = await conn.run_sync(_load)

    if "ai_sensitive_words" in table_cols:
        cols = table_cols["ai_sensitive_words"]
        if "updated_at" not in cols:
            await conn.execute(text(
                "ALTER TABLE ai_sensitive_words ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ))

    if "ai_prompt_configs" in table_cols:
        cols = table_cols["ai_prompt_configs"]
        if "display_name" not in cols:
            await conn.execute(text(
                "ALTER TABLE ai_prompt_configs ADD COLUMN display_name VARCHAR(100) NOT NULL DEFAULT ''"
            ))
        if "system_prompt" not in cols:
            await conn.execute(text(
                "ALTER TABLE ai_prompt_configs ADD COLUMN system_prompt TEXT NULL"
            ))

    if "ai_disclaimer_configs" in table_cols:
        cols = table_cols["ai_disclaimer_configs"]
        if "display_name" not in cols:
            await conn.execute(text(
                "ALTER TABLE ai_disclaimer_configs ADD COLUMN display_name VARCHAR(100) NOT NULL DEFAULT ''"
            ))
        if "disclaimer_text" not in cols:
            await conn.execute(text(
                "ALTER TABLE ai_disclaimer_configs ADD COLUMN disclaimer_text TEXT NULL"
            ))
        if "is_enabled" not in cols:
            await conn.execute(text(
                "ALTER TABLE ai_disclaimer_configs ADD COLUMN is_enabled BOOLEAN DEFAULT TRUE"
            ))


async def _sync_report_tables(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        result = {}
        for tbl in ["checkup_reports", "checkup_indicators", "ocr_configs", "report_alerts"]:
            if tbl in tables:
                result[tbl] = {col["name"] for col in inspector.get_columns(tbl)}
        return result, tables

    table_cols, all_tables = await conn.run_sync(_load)

    if "checkup_reports" in table_cols:
        cols = table_cols["checkup_reports"]
        if "thumbnail_url" not in cols:
            await conn.execute(text("ALTER TABLE checkup_reports ADD COLUMN thumbnail_url VARCHAR(500) NULL"))
        if "file_type" not in cols:
            await conn.execute(text("ALTER TABLE checkup_reports ADD COLUMN file_type VARCHAR(20) DEFAULT 'image'"))
        if "abnormal_count" not in cols:
            await conn.execute(text("ALTER TABLE checkup_reports ADD COLUMN abnormal_count INT DEFAULT 0"))
        if "share_token" not in cols:
            await conn.execute(text(
                "ALTER TABLE checkup_reports ADD COLUMN share_token VARCHAR(100) NULL UNIQUE"
            ))
        if "share_expires_at" not in cols:
            await conn.execute(text("ALTER TABLE checkup_reports ADD COLUMN share_expires_at DATETIME NULL"))
        if "ai_analysis_json" not in cols:
            await conn.execute(text("ALTER TABLE checkup_reports ADD COLUMN ai_analysis_json JSON NULL"))
        if "status" not in cols:
            await conn.execute(text("ALTER TABLE checkup_reports ADD COLUMN status VARCHAR(20) DEFAULT 'pending'"))

    if "checkup_indicators" in table_cols:
        cols = table_cols["checkup_indicators"]
        if "category" not in cols:
            await conn.execute(text("ALTER TABLE checkup_indicators ADD COLUMN category VARCHAR(100) NULL"))
        if "advice" not in cols:
            await conn.execute(text("ALTER TABLE checkup_indicators ADD COLUMN advice VARCHAR(500) NULL"))


async def _sync_ocr_detail_tables(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        result = {}
        for tbl in ["checkup_report_details", "drug_identify_details"]:
            if tbl in tables:
                result[tbl] = {col["name"] for col in inspector.get_columns(tbl)}
        return result

    table_cols = await conn.run_sync(_load)

    if "checkup_report_details" in table_cols:
        cols = table_cols["checkup_report_details"]
        if "abnormal_indicators" not in cols:
            await conn.execute(text("ALTER TABLE checkup_report_details ADD COLUMN abnormal_indicators JSON NULL"))
        if "ocr_call_record_id" not in cols:
            await conn.execute(text("ALTER TABLE checkup_report_details ADD COLUMN ocr_call_record_id INT NULL"))

    if "drug_identify_details" in table_cols:
        cols = table_cols["drug_identify_details"]
        if "ocr_call_record_id" not in cols:
            await conn.execute(text("ALTER TABLE drug_identify_details ADD COLUMN ocr_call_record_id INT NULL"))
        if "session_id" not in cols:
            await conn.execute(text("ALTER TABLE drug_identify_details ADD COLUMN session_id INT NULL"))
        if "status" not in cols:
            await conn.execute(text("ALTER TABLE drug_identify_details ADD COLUMN status VARCHAR(20) DEFAULT 'success'"))


async def _sync_ocr_call_records(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "ocr_call_records" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("ocr_call_records")}

    columns = await conn.run_sync(_load)
    if columns is None:
        return
    if "image_count" not in columns:
        await conn.execute(text(
            "ALTER TABLE ocr_call_records ADD COLUMN image_count INT NOT NULL DEFAULT 1"
        ))
    if "image_urls" not in columns:
        await conn.execute(text(
            "ALTER TABLE ocr_call_records ADD COLUMN image_urls JSON NULL"
        ))


async def _sync_ocr_scene_templates(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "ocr_scene_templates" not in tables:
            return None, []
        cols = {col["name"] for col in inspector.get_columns("ocr_scene_templates")}
        fks = inspector.get_foreign_keys("ocr_scene_templates")
        return cols, fks

    columns, fks = await conn.run_sync(_load)
    if columns is None:
        return

    if "ai_model_id" in columns or "ocr_provider" in columns:
        for fk in fks:
            if "ai_model_id" in fk.get("constrained_columns", []):
                fk_name = fk.get("name")
                if fk_name:
                    await conn.execute(text(
                        f"ALTER TABLE ocr_scene_templates DROP FOREIGN KEY {fk_name}"
                    ))

        drop_parts = []
        if "ai_model_id" in columns:
            drop_parts.append("DROP COLUMN ai_model_id")
        if "ocr_provider" in columns:
            drop_parts.append("DROP COLUMN ocr_provider")
        if drop_parts:
            await conn.execute(text(
                f"ALTER TABLE ocr_scene_templates {', '.join(drop_parts)}"
            ))


async def _sync_prompt_templates(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        return "prompt_templates" in set(inspector.get_table_names())

    exists = await conn.run_sync(_load)
    if not exists:
        await conn.execute(text(
            "CREATE TABLE prompt_templates ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "name VARCHAR(100) NOT NULL, "
            "prompt_type VARCHAR(50) NOT NULL, "
            "content TEXT NOT NULL, "
            "version INT DEFAULT 1, "
            "is_active BOOLEAN DEFAULT TRUE, "
            "parent_id INT NULL, "
            "preview_input TEXT NULL, "
            "created_by INT NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ")"
        ))


async def _sync_share_links(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        return "share_links" in set(inspector.get_table_names())

    exists = await conn.run_sync(_load)
    if not exists:
        await conn.execute(text(
            "CREATE TABLE share_links ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "link_token VARCHAR(64) NOT NULL UNIQUE, "
            "link_type VARCHAR(20) NOT NULL, "
            "record_id INT NOT NULL, "
            "user_id INT NOT NULL, "
            "view_count INT DEFAULT 0, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
            ")"
        ))


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
    await _sync_member_levels(conn)
    await _sync_sms_tables(conn)
    await _sync_chat_session_fields(conn)
    await _sync_knowledge_tables(conn)
    await _sync_ai_center_tables(conn)
    await _sync_report_tables(conn)
    await _sync_ocr_detail_tables(conn)
    await _sync_ocr_call_records(conn)
    await _sync_ocr_scene_templates(conn)
    await _sync_prompt_templates(conn)
    await _sync_share_links(conn)

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
