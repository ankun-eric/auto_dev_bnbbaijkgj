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
        if "health_score" not in cols:
            await conn.execute(text("ALTER TABLE checkup_reports ADD COLUMN health_score INT NULL"))
        if "family_member_id" not in cols:
            await conn.execute(text(
                "ALTER TABLE checkup_reports ADD COLUMN family_member_id INT NULL, "
                "ADD INDEX ix_checkup_reports_family_member_id (family_member_id), "
                "ADD CONSTRAINT fk_checkup_reports_family_member FOREIGN KEY (family_member_id) REFERENCES family_members(id)"
            ))

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


async def _sync_home_tables(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        result = {}
        for tbl in ["home_menu_items", "home_banners"]:
            if tbl in tables:
                result[tbl] = {col["name"] for col in inspector.get_columns(tbl)}
        return result, tables

    table_cols, all_tables = await conn.run_sync(_load)

    if "home_menu_items" not in all_tables:
        await conn.execute(text(
            "CREATE TABLE home_menu_items ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "name VARCHAR(20) NOT NULL, "
            "icon_type ENUM('emoji','image') NOT NULL DEFAULT 'emoji', "
            "icon_content VARCHAR(500) NOT NULL, "
            "link_type ENUM('internal','external','miniprogram') NOT NULL DEFAULT 'internal', "
            "link_url VARCHAR(500) NOT NULL, "
            "miniprogram_appid VARCHAR(100) NULL, "
            "sort_order INT NOT NULL DEFAULT 0, "
            "is_visible BOOLEAN NOT NULL DEFAULT TRUE, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ")"
        ))

    if "home_banners" not in all_tables:
        await conn.execute(text(
            "CREATE TABLE home_banners ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "image_url VARCHAR(500) NOT NULL, "
            "link_type ENUM('none','internal','external','miniprogram') NOT NULL DEFAULT 'none', "
            "link_url VARCHAR(500) NULL, "
            "miniprogram_appid VARCHAR(100) NULL, "
            "sort_order INT NOT NULL DEFAULT 0, "
            "is_visible BOOLEAN NOT NULL DEFAULT TRUE, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ")"
        ))


async def _sync_search_tables(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        result = {}
        for tbl in [
            "search_histories", "search_hot_words", "search_recommend_words",
            "search_block_words", "search_logs", "asr_configs", "drug_search_keywords",
        ]:
            if tbl in tables:
                result[tbl] = {col["name"] for col in inspector.get_columns(tbl)}
        return result, tables

    table_cols, all_tables = await conn.run_sync(_load)

    if "search_histories" in table_cols:
        cols = table_cols["search_histories"]
        if "search_count" not in cols:
            await conn.execute(text("ALTER TABLE search_histories ADD COLUMN search_count INT DEFAULT 1"))
        if "updated_at" not in cols:
            await conn.execute(text("ALTER TABLE search_histories ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"))

    if "search_hot_words" in table_cols:
        cols = table_cols["search_hot_words"]
        if "result_count" not in cols:
            await conn.execute(text("ALTER TABLE search_hot_words ADD COLUMN result_count INT DEFAULT 0"))
        if "category_hint" not in cols:
            await conn.execute(text("ALTER TABLE search_hot_words ADD COLUMN category_hint VARCHAR(50) NULL"))

    if "search_recommend_words" in table_cols:
        cols = table_cols["search_recommend_words"]
        if "category_hint" not in cols:
            await conn.execute(text("ALTER TABLE search_recommend_words ADD COLUMN category_hint VARCHAR(50) NULL"))

    if "search_logs" in table_cols:
        cols = table_cols["search_logs"]
        if "result_counts_json" not in cols:
            await conn.execute(text("ALTER TABLE search_logs ADD COLUMN result_counts_json TEXT NULL"))
        if "source" not in cols:
            await conn.execute(text("ALTER TABLE search_logs ADD COLUMN source VARCHAR(20) DEFAULT 'text'"))
        if "ip_address" not in cols:
            await conn.execute(text("ALTER TABLE search_logs ADD COLUMN ip_address VARCHAR(50) NULL"))

    if "asr_configs" in table_cols:
        cols = table_cols["asr_configs"]
        if "supported_dialects" not in cols:
            await conn.execute(text("ALTER TABLE asr_configs ADD COLUMN supported_dialects VARCHAR(200) DEFAULT '普通话,粤语'"))


async def _sync_health_profile_v2_fields(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "health_profiles" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("health_profiles")}

    columns = await conn.run_sync(_load)
    if columns is None:
        return
    if "name" not in columns:
        await conn.execute(text("ALTER TABLE health_profiles ADD COLUMN name VARCHAR(100) NULL"))
    if "chronic_diseases" not in columns:
        await conn.execute(text("ALTER TABLE health_profiles ADD COLUMN chronic_diseases JSON NULL"))
    if "drug_allergies" not in columns:
        await conn.execute(text("ALTER TABLE health_profiles ADD COLUMN drug_allergies TEXT NULL"))
    if "food_allergies" not in columns:
        await conn.execute(text("ALTER TABLE health_profiles ADD COLUMN food_allergies TEXT NULL"))
    if "other_allergies" not in columns:
        await conn.execute(text("ALTER TABLE health_profiles ADD COLUMN other_allergies TEXT NULL"))
    if "genetic_diseases" not in columns:
        await conn.execute(text("ALTER TABLE health_profiles ADD COLUMN genetic_diseases JSON NULL"))


async def _sync_family_member_v2_fields(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "family_members" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("family_members")}

    columns = await conn.run_sync(_load)
    if columns is None:
        return
    if "is_self" not in columns:
        await conn.execute(text("ALTER TABLE family_members ADD COLUMN is_self BOOLEAN NOT NULL DEFAULT FALSE"))
    if "relation_type_id" not in columns:
        await conn.execute(text("ALTER TABLE family_members ADD COLUMN relation_type_id INT NULL"))


async def _sync_relation_types_table(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        return "relation_types" in set(inspector.get_table_names())

    exists = await conn.run_sync(_load)
    if not exists:
        await conn.execute(text(
            "CREATE TABLE relation_types ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "name VARCHAR(50) NOT NULL, "
            "sort_order INT DEFAULT 0, "
            "is_active BOOLEAN DEFAULT TRUE, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ")"
        ))


async def _sync_disease_presets_table(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        return "disease_presets" in set(inspector.get_table_names())

    exists = await conn.run_sync(_load)
    if not exists:
        await conn.execute(text(
            "CREATE TABLE disease_presets ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "name VARCHAR(100) NOT NULL, "
            "category VARCHAR(20) NOT NULL, "
            "sort_order INT DEFAULT 0, "
            "is_active BOOLEAN DEFAULT TRUE, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ")"
        ))


async def _sync_notice_table(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        return "home_notices" in set(inspector.get_table_names())

    exists = await conn.run_sync(_load)
    if not exists:
        await conn.execute(text(
            "CREATE TABLE home_notices ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "content TEXT NOT NULL, "
            "link_url VARCHAR(500) NULL, "
            "start_time DATETIME NOT NULL, "
            "end_time DATETIME NOT NULL, "
            "is_enabled BOOLEAN NOT NULL DEFAULT TRUE, "
            "sort_order INT NOT NULL DEFAULT 0, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ")"
        ))


async def _sync_merchant_profile_shop_v2(conn: AsyncConnection) -> None:
    """[2026-04-25] 商家个人信息回填 + H5 店铺信息可编辑

    - users 表新增 last_login_at 字段，用于个人信息页"最近登录"展示
    - merchant_stores 表新增 logo_url / description / business_hours / license_no / legal_person
      字段，用于 H5 店铺信息编辑页
    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        users_cols = (
            {col["name"] for col in inspector.get_columns("users")}
            if "users" in tables else None
        )
        store_cols = (
            {col["name"] for col in inspector.get_columns("merchant_stores")}
            if "merchant_stores" in tables else None
        )
        return users_cols, store_cols

    users_cols, store_cols = await conn.run_sync(_load)
    if users_cols is not None and "last_login_at" not in users_cols:
        await conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at DATETIME NULL"))

    if store_cols is not None:
        if "logo_url" not in store_cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN logo_url VARCHAR(500) NULL"))
        if "description" not in store_cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN description VARCHAR(500) NULL"))
        if "business_hours" not in store_cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN business_hours VARCHAR(100) NULL"))
        if "license_no" not in store_cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN license_no VARCHAR(100) NULL"))
        if "legal_person" not in store_cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN legal_person VARCHAR(100) NULL"))


async def run_all_migrations(conn: AsyncConnection) -> None:
    await _sync_relation_types_table(conn)
    await _sync_disease_presets_table(conn)
    await _sync_family_member_v2_fields(conn)
    await _sync_health_profile_v2_fields(conn)
    await _sync_merchant_profile_shop_v2(conn)


async def _sync_bottom_nav_table(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        return "bottom_nav_config" in set(inspector.get_table_names())

    exists = await conn.run_sync(_load)
    if not exists:
        await conn.execute(text(
            "CREATE TABLE bottom_nav_config ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "name VARCHAR(20) NOT NULL, "
            "icon_key VARCHAR(50) NOT NULL, "
            "path VARCHAR(200) NOT NULL, "
            "sort_order INT NOT NULL DEFAULT 0, "
            "is_visible BOOLEAN NOT NULL DEFAULT TRUE, "
            "is_fixed BOOLEAN NOT NULL DEFAULT FALSE, "
            "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ")"
        ))


async def _sync_cos_config_fields(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "cos_configs" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("cos_configs")}

    columns = await conn.run_sync(_load)
    if columns is None:
        return

    if "cdn_domain" not in columns:
        await conn.execute(text("ALTER TABLE cos_configs ADD COLUMN cdn_domain VARCHAR(300) NULL"))
    if "cdn_protocol" not in columns:
        await conn.execute(text("ALTER TABLE cos_configs ADD COLUMN cdn_protocol VARCHAR(10) DEFAULT 'https'"))
    if "test_passed" not in columns:
        await conn.execute(text("ALTER TABLE cos_configs ADD COLUMN test_passed TINYINT(1) DEFAULT 0"))
    if "image_prefix" not in columns:
        await conn.execute(text("ALTER TABLE cos_configs ADD COLUMN image_prefix VARCHAR(200) DEFAULT 'images/'"))
    if "video_prefix" not in columns:
        await conn.execute(text("ALTER TABLE cos_configs ADD COLUMN video_prefix VARCHAR(200) DEFAULT 'videos/'"))
    if "file_prefix" not in columns:
        await conn.execute(text("ALTER TABLE cos_configs ADD COLUMN file_prefix VARCHAR(200) DEFAULT 'files/'"))
    if "path_prefix" in columns:
        await conn.execute(text("ALTER TABLE cos_configs DROP COLUMN path_prefix"))


async def _sync_drug_identify_family_member(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "drug_identify_details" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("drug_identify_details")}

    columns = await conn.run_sync(_load)
    if columns is None:
        return
    if "family_member_id" not in columns:
        await conn.execute(text(
            "ALTER TABLE drug_identify_details ADD COLUMN family_member_id INT NULL, "
            "ADD INDEX ix_drug_identify_details_family_member_id (family_member_id), "
            "ADD CONSTRAINT fk_drug_identify_details_family_member FOREIGN KEY (family_member_id) REFERENCES family_members(id)"
        ))


async def _sync_chat_share_records_table(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        return "chat_share_records" in set(inspector.get_table_names())

    exists = await conn.run_sync(_load)
    if not exists:
        await conn.execute(text(
            "CREATE TABLE chat_share_records ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "share_token VARCHAR(64) NOT NULL UNIQUE, "
            "session_id INT NOT NULL, "
            "user_message_id INT NOT NULL, "
            "ai_message_id INT NOT NULL, "
            "user_id INT NOT NULL, "
            "view_count INT DEFAULT 0, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "INDEX ix_chat_share_records_share_token (share_token), "
            "CONSTRAINT fk_chat_share_session FOREIGN KEY (session_id) REFERENCES chat_sessions(id), "
            "CONSTRAINT fk_chat_share_user_msg FOREIGN KEY (user_message_id) REFERENCES chat_messages(id), "
            "CONSTRAINT fk_chat_share_ai_msg FOREIGN KEY (ai_message_id) REFERENCES chat_messages(id), "
            "CONSTRAINT fk_chat_share_user FOREIGN KEY (user_id) REFERENCES users(id)"
            ")"
        ))


async def _sync_tcm_configs_table(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        return "tcm_configs" in set(inspector.get_table_names())

    exists = await conn.run_sync(_load)
    if not exists:
        await conn.execute(text(
            "CREATE TABLE tcm_configs ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "tongue_diagnosis_enabled BOOLEAN DEFAULT FALSE, "
            "face_diagnosis_enabled BOOLEAN DEFAULT FALSE, "
            "constitution_test_enabled BOOLEAN DEFAULT TRUE, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ")"
        ))


async def _sync_chat_function_button_fields(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "chat_function_buttons" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("chat_function_buttons")}

    columns = await conn.run_sync(_load)
    if columns is None:
        return
    if "ai_reply_mode" not in columns:
        await conn.execute(text(
            "ALTER TABLE chat_function_buttons ADD COLUMN ai_reply_mode VARCHAR(50) NULL DEFAULT 'complete_analysis'"
        ))
    if "photo_tip_text" not in columns:
        await conn.execute(text(
            "ALTER TABLE chat_function_buttons ADD COLUMN photo_tip_text VARCHAR(500) NULL "
            "DEFAULT '请确保药品名称、品牌、规格完整，拍摄清晰'"
        ))
    if "max_photo_count" not in columns:
        await conn.execute(text(
            "ALTER TABLE chat_function_buttons ADD COLUMN max_photo_count INT NULL DEFAULT 5"
        ))


async def _sync_tcm_diagnosis_fields(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "tcm_diagnoses" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("tcm_diagnoses")}

    columns = await conn.run_sync(_load)
    if columns is None:
        return
    if "family_member_id" not in columns:
        await conn.execute(text(
            "ALTER TABLE tcm_diagnoses ADD COLUMN family_member_id INT NULL, "
            "ADD INDEX ix_tcm_diagnoses_family_member_id (family_member_id), "
            "ADD CONSTRAINT fk_tcm_diagnoses_family_member FOREIGN KEY (family_member_id) REFERENCES family_members(id)"
        ))
    if "constitution_description" not in columns:
        await conn.execute(text(
            "ALTER TABLE tcm_diagnoses ADD COLUMN constitution_description VARCHAR(500) NULL"
        ))
    if "advice_summary" not in columns:
        await conn.execute(text(
            "ALTER TABLE tcm_diagnoses ADD COLUMN advice_summary VARCHAR(1000) NULL"
        ))


async def _sync_chat_message_metadata(conn: AsyncConnection) -> None:
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "chat_messages" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("chat_messages")}

    columns = await conn.run_sync(_load)
    if columns is None:
        return
    if "message_metadata" not in columns:
        await conn.execute(text(
            "ALTER TABLE chat_messages ADD COLUMN message_metadata JSON NULL"
        ))


async def _sync_product_system_tables(conn: AsyncConnection) -> None:
    """Sync new product/order/coupon system tables (add missing columns to existing tables)."""
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        result = {}
        for tbl in [
            "product_categories", "products", "product_stores",
            "appointment_forms", "appointment_form_fields",
            "unified_orders", "order_items", "order_redemptions",
            "user_addresses", "coupons", "user_coupons",
            "member_qr_tokens", "checkin_records", "store_visit_records",
            "refund_requests",
        ]:
            if tbl in tables:
                result[tbl] = {col["name"] for col in inspector.get_columns(tbl)}
        return result

    table_cols = await conn.run_sync(_load)

    if "products" in table_cols:
        cols = table_cols["products"]
        if "payment_timeout_minutes" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN payment_timeout_minutes INT DEFAULT 15"))
        if "purchase_appointment_mode" not in cols:
            await conn.execute(text(
                "ALTER TABLE products ADD COLUMN purchase_appointment_mode "
                "ENUM('purchase_with_appointment','appointment_later','must_appoint','appoint_later') NULL"
            ))
        else:
            # 枚举扩容：兼容新旧两套值（BUG-PRODUCT-APPT-001）
            try:
                await conn.execute(text(
                    "ALTER TABLE products MODIFY COLUMN purchase_appointment_mode "
                    "ENUM('purchase_with_appointment','appointment_later','must_appoint','appoint_later') NULL"
                ))
            except Exception:
                pass
        # ── 预约联动 UI 新增字段（BUG-PRODUCT-APPT-001）──
        if "advance_days" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN advance_days INT NULL"))
        if "daily_quota" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN daily_quota INT NULL"))
        if "time_slots" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN time_slots JSON NULL"))
        # ── BUG-PRODUCT-APPT-002：include_today 字段（date / time_slot 共用，默认 true）──
        if "include_today" not in cols:
            await conn.execute(text(
                "ALTER TABLE products ADD COLUMN include_today TINYINT(1) NOT NULL DEFAULT 1 "
                "COMMENT '预约起始日是否包含今天，默认 true'"
            ))
        # ── 历史数据兜底（幂等）：time_slot 模式 advance_days 为空 → 7 天 ──
        try:
            await conn.execute(text(
                "UPDATE products SET advance_days = 7 "
                "WHERE appointment_mode = 'time_slot' "
                "AND (advance_days IS NULL OR advance_days <= 0)"
            ))
        except Exception:
            pass
        try:
            await conn.execute(text(
                "UPDATE products SET advance_days = 7 "
                "WHERE appointment_mode = 'date' "
                "AND (advance_days IS NULL OR advance_days <= 0)"
            ))
        except Exception:
            pass
        # ── 预约模式枚举对齐：MySQL ENUM 扩容 + 旧值清洗（BUG-PRODUCT-APPT-001）──
        try:
            await conn.execute(text(
                "ALTER TABLE products MODIFY COLUMN appointment_mode "
                "ENUM('none','date','time_slot','custom_form','schedule','free_time','walk_in') "
                "NOT NULL DEFAULT 'none'"
            ))
        except Exception:
            pass
        # 将过期的旧值重写为 none，避免 ORM LookupError
        try:
            await conn.execute(text(
                "UPDATE products SET appointment_mode = 'none' "
                "WHERE appointment_mode IN ('schedule','free_time','walk_in')"
            ))
        except Exception:
            pass
        # 最终再次收缩为目标枚举
        try:
            await conn.execute(text(
                "ALTER TABLE products MODIFY COLUMN appointment_mode "
                "ENUM('none','date','time_slot','custom_form') NOT NULL DEFAULT 'none'"
            ))
        except Exception:
            pass
        # ── 商品弹窗优化 v2 新增字段 ──
        if "product_code_list" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN product_code_list JSON NULL"))
        if "spec_mode" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN spec_mode TINYINT DEFAULT 1"))
        if "main_video_url" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN main_video_url VARCHAR(500) NULL"))
        if "selling_point" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN selling_point VARCHAR(200) NULL"))
        if "description_rich" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN description_rich TEXT NULL"))
        # ── 商品功能优化 v1.0：营销角标（limited/hot/new/recommend） ──
        if "marketing_badges" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN marketing_badges JSON NULL"))
        # ── 商品功能优化 v1.0：彻底清理有效日期字段（用户选择 C. 彻底清空） ──
        # 幂等执行：列存在则 DROP；不存在则跳过。所有异常静默处理（例如 MySQL 不同版本的语法差异）
        if "valid_start_date" in cols:
            try:
                await conn.execute(text("ALTER TABLE products DROP COLUMN valid_start_date"))
            except Exception:
                pass
        if "valid_end_date" in cols:
            try:
                await conn.execute(text("ALTER TABLE products DROP COLUMN valid_end_date"))
            except Exception:
                pass

    # ── 预约表单库：为 appointment_forms 增加 status 列（BUG-PRODUCT-APPT-001）──
    if "appointment_forms" in table_cols:
        af_cols = table_cols["appointment_forms"]
        if "status" not in af_cols:
            await conn.execute(text(
                "ALTER TABLE appointment_forms ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"
            ))

    # 创建 product_skus 表（如果不存在）
    def _check_sku_table(sync_conn):
        inspector = inspect(sync_conn)
        return "product_skus" in set(inspector.get_table_names())

    has_sku_table = await conn.run_sync(_check_sku_table)
    if not has_sku_table:
        await conn.execute(text("""
            CREATE TABLE product_skus (
                id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                product_id INT NOT NULL,
                spec_name VARCHAR(50) NOT NULL,
                sale_price DECIMAL(10,2) NOT NULL DEFAULT 0,
                origin_price DECIMAL(10,2) NULL,
                stock INT DEFAULT 0,
                is_default BOOLEAN DEFAULT FALSE,
                status TINYINT DEFAULT 1,
                sort_order INT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX ix_product_skus_product_id (product_id),
                UNIQUE KEY uq_product_sku_name (product_id, spec_name),
                CONSTRAINT fk_product_sku_product FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """))


    if "unified_orders" in table_cols:
        cols = table_cols["unified_orders"]
        if "auto_confirm_days" not in cols:
            await conn.execute(text("ALTER TABLE unified_orders ADD COLUMN auto_confirm_days INT DEFAULT 7"))
        if "payment_timeout_minutes" not in cols:
            await conn.execute(text("ALTER TABLE unified_orders ADD COLUMN payment_timeout_minutes INT DEFAULT 15"))
        if "has_reviewed" not in cols:
            await conn.execute(text("ALTER TABLE unified_orders ADD COLUMN has_reviewed BOOLEAN DEFAULT FALSE"))

    if "order_items" in table_cols:
        cols = table_cols["order_items"]
        if "verification_qrcode_token" not in cols:
            await conn.execute(text("ALTER TABLE order_items ADD COLUMN verification_qrcode_token VARCHAR(100) NULL"))
        if "total_redeem_count" not in cols:
            await conn.execute(text("ALTER TABLE order_items ADD COLUMN total_redeem_count INT DEFAULT 1"))
        if "used_redeem_count" not in cols:
            await conn.execute(text("ALTER TABLE order_items ADD COLUMN used_redeem_count INT DEFAULT 0"))
        if "sku_id" not in cols:
            await conn.execute(text("ALTER TABLE order_items ADD COLUMN sku_id BIGINT NULL"))
            try:
                await conn.execute(text("CREATE INDEX ix_order_items_sku_id ON order_items (sku_id)"))
            except Exception:
                pass
        if "sku_name" not in cols:
            await conn.execute(text("ALTER TABLE order_items ADD COLUMN sku_name VARCHAR(50) NULL"))

    if "refund_requests" in table_cols:
        cols = table_cols["refund_requests"]
        if "return_tracking_number" not in cols:
            await conn.execute(text("ALTER TABLE refund_requests ADD COLUMN return_tracking_number VARCHAR(100) NULL"))
        if "return_tracking_company" not in cols:
            await conn.execute(text("ALTER TABLE refund_requests ADD COLUMN return_tracking_company VARCHAR(100) NULL"))
        if "has_redemption" not in cols:
            await conn.execute(text("ALTER TABLE refund_requests ADD COLUMN has_redemption TINYINT(1) DEFAULT 0"))
        if "refund_amount_approved" not in cols:
            await conn.execute(text("ALTER TABLE refund_requests ADD COLUMN refund_amount_approved DECIMAL(10,2) NULL"))
        try:
            await conn.execute(text(
                "ALTER TABLE refund_requests MODIFY COLUMN status "
                "ENUM('pending','reviewing','approved','rejected','returning','completed','withdrawn') "
                "NOT NULL DEFAULT 'pending'"
            ))
        except Exception:
            pass


async def _sync_merchant_v1_backend(conn: AsyncConnection) -> None:
    """v1 商家后台 + 机构体系：
    - MerchantMemberRole 扩展 ENUM: owner/staff/store_manager/verifier/finance
    - merchant_profiles 新增 category_id
    - 其他新表由 metadata.create_all 自动创建
    - 初始化默认 merchant_categories
    [2026-04-24] 扩展：
    - merchant_stores 新增 category_id
    - merchant_store_memberships 新增 role_code
    - 新增 merchant_role_templates 表 + 4 条默认角色
    - 存量 membership 自动回填 role_code
    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        mp_cols = None
        if "merchant_profiles" in tables:
            mp_cols = {c["name"] for c in inspector.get_columns("merchant_profiles")}
        ms_cols = None
        if "merchant_stores" in tables:
            ms_cols = {c["name"] for c in inspector.get_columns("merchant_stores")}
        mem_cols = None
        if "merchant_store_memberships" in tables:
            mem_cols = {c["name"] for c in inspector.get_columns("merchant_store_memberships")}
        return tables, mp_cols, ms_cols, mem_cols

    tables, mp_cols, ms_cols, mem_cols = await conn.run_sync(_load)

    # ENUM 扩展（MySQL：MODIFY COLUMN 为新 ENUM）
    if "merchant_store_memberships" in tables:
        try:
            await conn.execute(text(
                "ALTER TABLE merchant_store_memberships MODIFY COLUMN member_role "
                "ENUM('owner','staff','store_manager','verifier','finance') NOT NULL"
            ))
        except Exception:
            pass

    if mp_cols is not None and "category_id" not in mp_cols:
        try:
            await conn.execute(text("ALTER TABLE merchant_profiles ADD COLUMN category_id INT NULL"))
            await conn.execute(text("CREATE INDEX ix_mp_category ON merchant_profiles(category_id)"))
        except Exception:
            pass

    # [2026-04-24] merchant_stores 新增 category_id
    if ms_cols is not None and "category_id" not in ms_cols:
        try:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN category_id INT NULL"))
            await conn.execute(text("CREATE INDEX ix_ms_category ON merchant_stores(category_id)"))
        except Exception:
            pass

    # [2026-04-24] merchant_store_memberships 新增 role_code
    if mem_cols is not None and "role_code" not in mem_cols:
        try:
            await conn.execute(text("ALTER TABLE merchant_store_memberships ADD COLUMN role_code VARCHAR(32) NULL"))
            await conn.execute(text("CREATE INDEX ix_mem_role_code ON merchant_store_memberships(role_code)"))
        except Exception:
            pass

    # 默认机构类别（幂等）
    if "merchant_categories" in tables:
        default_cats = [
            ("self_store", "自营门店", "🏪", ["image", "pdf"], "附件", 10),
            ("medical", "体检机构", "🏥", ["image", "pdf"], "检查报告", 20),
            ("homeservice", "家政机构", "🧹", ["image", "pdf"], "服务工单", 30),
            ("other", "其他机构", "🏷️", ["image", "pdf"], "附件", 99),
        ]
        for code, name, icon, atypes, label, sort in default_cats:
            try:
                rs = await conn.execute(text("SELECT id FROM merchant_categories WHERE code=:c"), {"c": code})
                if rs.fetchone() is None:
                    import json as _json
                    await conn.execute(
                        text(
                            "INSERT INTO merchant_categories(code, name, icon, allowed_attachment_types, "
                            "attachment_label, sort, status, created_at, updated_at) "
                            "VALUES(:code, :name, :icon, :atypes, :label, :sort, 'active', NOW(), NOW())"
                        ),
                        {"code": code, "name": name, "icon": icon, "atypes": _json.dumps(atypes),
                         "label": label, "sort": sort},
                    )
            except Exception:
                pass

    # [2026-04-24] 默认角色模板（幂等插入 + 回填存量 membership）
    # 重新读取 tables 以包含新创建的 merchant_role_templates
    def _tables_only(sync_conn):
        return set(inspect(sync_conn).get_table_names())
    tables2 = await conn.run_sync(_tables_only)
    if "merchant_role_templates" in tables2:
        import json as _json
        # 8 模块体系（与 admin_merchant.FULL_MODULE_CODES 保持一致）
        default_roles = [
            ("boss", "老板", ["dashboard", "verify", "records", "messages", "profile", "finance", "staff", "settings"], 10),
            ("manager", "店长", ["dashboard", "verify", "records", "messages", "profile", "finance", "staff", "settings"], 20),
            ("finance", "财务", ["dashboard", "records", "messages", "profile", "finance"], 30),
            ("clerk", "店员", ["dashboard", "verify", "records", "messages", "profile"], 40),
        ]
        for code, name, modules, sort_order in default_roles:
            try:
                rs = await conn.execute(
                    text("SELECT id, default_modules FROM merchant_role_templates WHERE code=:c"),
                    {"c": code},
                )
                row = rs.fetchone()
                if row is None:
                    await conn.execute(
                        text(
                            "INSERT INTO merchant_role_templates(code, name, default_modules, is_system, sort_order, created_at, updated_at) "
                            "VALUES(:code, :name, :modules, 1, :sort, NOW(), NOW())"
                        ),
                        {"code": code, "name": name, "modules": _json.dumps(modules), "sort": sort_order},
                    )
            except Exception:
                pass

        # 回填 membership.role_code：owner->boss，其它->clerk（不覆盖已有值）
        if mem_cols is not None:
            try:
                await conn.execute(text(
                    "UPDATE merchant_store_memberships SET role_code='boss' "
                    "WHERE member_role='owner' AND (role_code IS NULL OR role_code='')"
                ))
                await conn.execute(text(
                    "UPDATE merchant_store_memberships SET role_code='clerk' "
                    "WHERE member_role<>'owner' AND (role_code IS NULL OR role_code='')"
                ))
            except Exception:
                pass


async def _sync_settlement_proof_schema(conn: AsyncConnection) -> None:
    """[2026-04-24] 对账单凭证扩展：新增 voucher_type / voucher_files / remark / updated_at 列；
    file_url 放宽为可空（以支持新模式只存 voucher_files 而不存单一 file_url）。
    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "settlement_payment_proofs" not in tables:
            return set()
        return {c["name"] for c in inspector.get_columns("settlement_payment_proofs")}

    cols = await conn.run_sync(_load)
    if not cols:
        return
    try:
        if "voucher_type" not in cols:
            await conn.execute(text(
                "ALTER TABLE settlement_payment_proofs ADD COLUMN voucher_type VARCHAR(16) NULL"
            ))
        if "voucher_files" not in cols:
            await conn.execute(text(
                "ALTER TABLE settlement_payment_proofs ADD COLUMN voucher_files JSON NULL"
            ))
        if "remark" not in cols:
            await conn.execute(text(
                "ALTER TABLE settlement_payment_proofs ADD COLUMN remark TEXT NULL"
            ))
        if "updated_at" not in cols:
            await conn.execute(text(
                "ALTER TABLE settlement_payment_proofs ADD COLUMN updated_at DATETIME NULL"
            ))
        try:
            await conn.execute(text(
                "ALTER TABLE settlement_payment_proofs MODIFY COLUMN file_url VARCHAR(500) NULL"
            ))
        except Exception:
            pass
    except Exception:
        pass


async def _sync_card_face_fields(conn: AsyncConnection) -> None:
    """[2026-05-03 卡管理 PRD v1.1] card_definitions 新增卡面设置 4 字段。
    增量、幂等。老数据按默认值回填。
    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "card_definitions" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("card_definitions")}

    columns = await conn.run_sync(_load)
    if columns is None:
        return

    if "face_style" not in columns:
        await conn.execute(text(
            "ALTER TABLE card_definitions ADD COLUMN face_style VARCHAR(8) NOT NULL DEFAULT 'ST1' "
            "COMMENT '卡面样式 ST1~ST4'"
        ))
    if "face_bg_code" not in columns:
        await conn.execute(text(
            "ALTER TABLE card_definitions ADD COLUMN face_bg_code VARCHAR(8) NOT NULL DEFAULT 'BG1' "
            "COMMENT '卡面背景 BG1~BG8'"
        ))
    if "face_show_flags" not in columns:
        await conn.execute(text(
            "ALTER TABLE card_definitions ADD COLUMN face_show_flags INT NOT NULL DEFAULT 7 "
            "COMMENT '4 项显示位 bitmask；默认 7=SH1+SH2+SH3'"
        ))
    if "face_layout" not in columns:
        await conn.execute(text(
            "ALTER TABLE card_definitions ADD COLUMN face_layout VARCHAR(8) NOT NULL DEFAULT 'ON_CARD' "
            "COMMENT '信息布局，本期固定 ON_CARD'"
        ))


async def _sync_orders_status_v2(conn: AsyncConnection) -> None:
    """[2026-05-03 PRD V2 核销订单状态体系优化]
    1) order_items 新增 redemption_code_status / redemption_code_expires_at
    2) unified_orders.status ENUM 扩列到 12 值（保留 pending_review 兼容）
    3) 一次性数据迁移（用 system_configs 标记版本号，幂等）：
       - pending_review → completed（V2 取消"待评价"独立状态）
       - 待核销 + 已过期：pending_use 且 redemption_code_expires_at 已过 → expired
       - 退款融合：refund_status=refund_success 且 status!=cancelled → refunded
                  refund_status=applied/reviewing/returning 且 status!=cancelled → refunding
    所有操作均为 try/except + warn，缺字段时跳过该条规则。
    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        result = {
            "order_items": None,
            "unified_orders": None,
            "system_configs": None,
        }
        for tbl in result:
            if tbl in tables:
                result[tbl] = {col["name"] for col in inspector.get_columns(tbl)}
        return result

    table_cols = await conn.run_sync(_load)

    # ── 1) order_items 加列 ──
    if table_cols.get("order_items") is not None:
        cols = table_cols["order_items"]
        if "redemption_code_status" not in cols:
            await conn.execute(text(
                "ALTER TABLE order_items ADD COLUMN redemption_code_status "
                "VARCHAR(16) NOT NULL DEFAULT 'active' "
                "COMMENT '核销码 5 态：active/locked/used/expired/refunded（PRD V2）'"
            ))
            await conn.execute(text(
                "CREATE INDEX ix_order_items_redemption_code_status "
                "ON order_items(redemption_code_status)"
            ))
        if "redemption_code_expires_at" not in cols:
            await conn.execute(text(
                "ALTER TABLE order_items ADD COLUMN redemption_code_expires_at "
                "DATETIME NULL COMMENT '核销码过期时间（PRD V2）'"
            ))

    # ── 2) unified_orders.status ENUM 扩列 ──
    if table_cols.get("unified_orders") is not None:
        # MySQL：MODIFY ENUM 把所有 12 + 1（pending_review 兼容）枚举值列出
        # 在 SQLite 下不存在 ENUM 概念，UnifiedOrderStatus 的 String 比较仍能工作；
        # 为兼容性此处仅在 MySQL 方言下执行。
        try:
            dialect_name = conn.dialect.name  # "mysql" / "sqlite" / ...
        except Exception:
            dialect_name = ""
        if dialect_name == "mysql":
            try:
                await conn.execute(text(
                    "ALTER TABLE unified_orders MODIFY COLUMN status ENUM("
                    "'pending_payment','pending_shipment','pending_receipt',"
                    "'pending_appointment','appointed','pending_use','partial_used',"
                    "'pending_review','completed','expired','refunding','refunded',"
                    "'cancelled') NOT NULL DEFAULT 'pending_payment'"
                ))
            except Exception as e:
                # 即使 ALTER 失败（已经是更宽的枚举），也允许继续
                print(f"[schema_sync] _sync_orders_status_v2 ALTER status enum warn: {e}")

    # ── 3) 一次性数据迁移：版本号写入 system_configs ──
    MIGRATION_KEY = "orders_status_v2_migration_version"
    MIGRATION_VAL = "1"

    has_sysconf = table_cols.get("system_configs") is not None
    already_migrated = False
    if has_sysconf:
        try:
            row = (await conn.execute(text(
                "SELECT config_value FROM system_configs WHERE config_key = :k"
            ), {"k": MIGRATION_KEY})).fetchone()
            if row and (row[0] == MIGRATION_VAL):
                already_migrated = True
        except Exception:
            # system_configs 列名可能不同；尝试备选
            try:
                row = (await conn.execute(text(
                    "SELECT value FROM system_configs WHERE `key` = :k"
                ), {"k": MIGRATION_KEY})).fetchone()
                if row and (row[0] == MIGRATION_VAL):
                    already_migrated = True
            except Exception:
                already_migrated = False

    if already_migrated:
        return

    # 真正执行迁移
    if table_cols.get("unified_orders") is None:
        return  # 没有该表，整体跳过

    uo_cols = table_cols["unified_orders"]

    # 规则 1：pending_review → completed
    try:
        r = await conn.execute(text(
            "UPDATE unified_orders SET status='completed' "
            "WHERE status='pending_review'"
        ))
        print(f"[orders_v2 migrate] pending_review→completed rows={r.rowcount}")
    except Exception as e:
        print(f"[orders_v2 migrate] pending_review→completed skip: {e}")

    # 规则 2：refund_status=refund_success 且 status!=cancelled → refunded
    if "refund_status" in uo_cols:
        try:
            r = await conn.execute(text(
                "UPDATE unified_orders SET status='refunded' "
                "WHERE refund_status='refund_success' AND status<>'cancelled' "
                "AND status<>'refunded'"
            ))
            print(f"[orders_v2 migrate] refund_success→refunded rows={r.rowcount}")
        except Exception as e:
            print(f"[orders_v2 migrate] refund_success→refunded skip: {e}")

        # 规则 3：refund_status in (applied/reviewing/returning) → refunding
        try:
            r = await conn.execute(text(
                "UPDATE unified_orders SET status='refunding' "
                "WHERE refund_status IN ('applied','reviewing','returning') "
                "AND status NOT IN ('cancelled','refunded','refunding')"
            ))
            print(f"[orders_v2 migrate] refund_in_progress→refunding rows={r.rowcount}")
        except Exception as e:
            print(f"[orders_v2 migrate] refund_in_progress→refunding skip: {e}")

    # 规则 4：pending_use + redemption_code_expires_at 过期 → expired
    if "redemption_code_expires_at" in (table_cols.get("order_items") or set()):
        try:
            r = await conn.execute(text(
                "UPDATE unified_orders uo SET status='expired' "
                "WHERE uo.status='pending_use' AND EXISTS ("
                "  SELECT 1 FROM order_items oi WHERE oi.order_id=uo.id "
                "  AND oi.redemption_code_expires_at IS NOT NULL "
                "  AND oi.redemption_code_expires_at < NOW()"
                ")"
            ))
            print(f"[orders_v2 migrate] pending_use_expired→expired rows={r.rowcount}")
        except Exception as e:
            print(f"[orders_v2 migrate] pending_use_expired→expired skip: {e}")

    # 写入版本号（已迁移）
    if has_sysconf:
        try:
            await conn.execute(text(
                "INSERT INTO system_configs (config_key, config_value, description, created_at, updated_at) "
                "VALUES (:k, :v, 'orders_status_v2 migration done', NOW(), NOW()) "
                "ON DUPLICATE KEY UPDATE config_value=:v, updated_at=NOW()"
            ), {"k": MIGRATION_KEY, "v": MIGRATION_VAL})
        except Exception as e:
            # SQLite 不支持 ON DUPLICATE KEY；做一次普通的 INSERT OR REPLACE
            try:
                await conn.execute(text(
                    "INSERT OR REPLACE INTO system_configs (config_key, config_value) "
                    "VALUES (:k, :v)"
                ), {"k": MIGRATION_KEY, "v": MIGRATION_VAL})
            except Exception as e2:
                print(f"[orders_v2 migrate] write version flag skip: {e}/{e2}")


async def _sync_store_bindding_tables(conn: AsyncConnection) -> None:
    """门店绑定与订单通知增强：新增字段与表。"""
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        result = {}
        for tbl in [
            "merchant_stores", "merchant_notifications", "unified_orders",
            "staff_wechat_bindings", "order_notes", "order_appointment_logs",
        ]:
            if tbl in tables:
                result[tbl] = {col["name"] for col in inspector.get_columns(tbl)}
            else:
                result[tbl] = None
        return result

    table_cols = await conn.run_sync(_load)

    # 1. merchant_stores 新增 business_scope
    if table_cols.get("merchant_stores") is not None:
        cols = table_cols["merchant_stores"]
        if "business_scope" not in cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN business_scope JSON NULL"))
        if "lat" not in cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN lat DECIMAL(10,6) NULL"))
        if "lng" not in cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN lng DECIMAL(10,6) NULL"))
        # [2026-05-01 门店地图能力 PRD v1.0] 省/市/区拆分字段
        if "province" not in cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN province VARCHAR(50) NULL"))
        if "city" not in cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN city VARCHAR(50) NULL"))
        if "district" not in cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN district VARCHAR(50) NULL"))
        # [2026-05-02 H5 下单流程优化 PRD v1.0] 单时段最大接单数 + 营业起止时间
        if "slot_capacity" not in cols:
            await conn.execute(text(
                "ALTER TABLE merchant_stores ADD COLUMN slot_capacity INT NOT NULL DEFAULT 10 "
                "COMMENT '单时段最大接单数，默认 10'"
            ))
        if "business_start" not in cols:
            await conn.execute(text(
                "ALTER TABLE merchant_stores ADD COLUMN business_start VARCHAR(5) NULL "
                "COMMENT '营业开始 HH:MM'"
            ))
        if "business_end" not in cols:
            await conn.execute(text(
                "ALTER TABLE merchant_stores ADD COLUMN business_end VARCHAR(5) NULL "
                "COMMENT '营业结束 HH:MM'"
            ))

        # ════════════════════════════════════════════════════════════
        # [2026-05-03 营业时间/营业范围保存 Bug 修复] 一次性数据迁移：
        # 把现网 business_hours 字符串解析回填到 business_start / business_end。
        # 解析失败的保留原值，business_start/business_end 留空，等商家上线后自行选填。
        # ════════════════════════════════════════════════════════════
        try:
            rows = (await conn.execute(text(
                "SELECT id, business_hours, business_start, business_end "
                "FROM merchant_stores "
                "WHERE business_hours IS NOT NULL "
                "  AND business_hours <> '' "
                "  AND (business_start IS NULL OR business_start = '' "
                "       OR business_end IS NULL OR business_end = '')"
            ))).fetchall()
            import re as _re
            migrated = 0
            skipped = 0
            for row in rows:
                store_id = row[0]
                hours_str = row[1] or ""
                # 仅匹配类似 "09:00 - 22:00" / "09:00-22:00" / "9:00~22:00" 等常见 ASCII 数字格式
                m = _re.match(
                    r"^\s*(\d{1,2}):(\d{2})\s*[-~至到 ]+\s*(\d{1,2}):(\d{2})\s*$",
                    hours_str,
                )
                if not m:
                    skipped += 1
                    continue
                sh, sm, eh, em = (int(m.group(1)), int(m.group(2)),
                                  int(m.group(3)), int(m.group(4)))
                if not (0 <= sh <= 23 and 0 <= eh <= 23 and sm in (0, 30) and em in (0, 30)):
                    # 非 30 分钟整点的，按"就近 30 分"对齐：mm<15→00, 15≤mm<45→30, mm≥45→下个小时
                    def _round_30(h, m_):
                        if m_ < 15:
                            return h, 0
                        if m_ < 45:
                            return h, 30
                        return min(h + 1, 23), 0
                    sh, sm = _round_30(sh, sm)
                    eh, em = _round_30(eh, em)
                bs_str = f"{sh:02d}:{sm:02d}"
                be_str = f"{eh:02d}:{em:02d}"
                # 限定到 07:00–22:00
                if bs_str < "07:00":
                    bs_str = "07:00"
                if be_str > "22:00":
                    be_str = "22:00"
                if be_str <= bs_str:
                    skipped += 1
                    continue
                await conn.execute(text(
                    "UPDATE merchant_stores SET business_start=:s, business_end=:e "
                    "WHERE id=:id"
                ), {"s": bs_str, "e": be_str, "id": store_id})
                migrated += 1
            if migrated or skipped:
                import logging as _logging
                _logging.getLogger(__name__).info(
                    "[migrate] business_hours -> business_start/end: migrated=%d skipped=%d",
                    migrated, skipped,
                )
        except Exception as _e:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "[migrate] business_hours migration failed: %s", _e
            )

    # 2. merchant_notifications 新增 notification_type
    if table_cols.get("merchant_notifications") is not None:
        cols = table_cols["merchant_notifications"]
        if "notification_type" not in cols:
            await conn.execute(text(
                "ALTER TABLE merchant_notifications ADD COLUMN notification_type VARCHAR(50) DEFAULT 'system'"
            ))

    # 3. unified_orders 新增 store_confirmed, store_confirmed_at, store_id
    if table_cols.get("unified_orders") is not None:
        cols = table_cols["unified_orders"]
        if "store_confirmed" not in cols:
            await conn.execute(text(
                "ALTER TABLE unified_orders ADD COLUMN store_confirmed BOOLEAN DEFAULT FALSE"
            ))
        if "store_confirmed_at" not in cols:
            await conn.execute(text(
                "ALTER TABLE unified_orders ADD COLUMN store_confirmed_at DATETIME NULL"
            ))
        if "store_id" not in cols:
            await conn.execute(text(
                "ALTER TABLE unified_orders ADD COLUMN store_id INT NULL"
            ))
            try:
                await conn.execute(text("CREATE INDEX ix_unified_orders_store_id ON unified_orders(store_id)"))
            except Exception:
                pass

    # 4. staff_wechat_bindings 表（由 metadata.create_all 处理，此处只加缺失列）
    if table_cols.get("staff_wechat_bindings") is None:
        await conn.execute(text(
            "CREATE TABLE staff_wechat_bindings ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "staff_id INT NOT NULL, "
            "store_id INT NOT NULL, "
            "openid VARCHAR(128) NOT NULL, "
            "bound_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "is_active BOOLEAN DEFAULT TRUE, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "INDEX ix_swb_staff_id (staff_id), "
            "INDEX ix_swb_store_id (store_id), "
            "CONSTRAINT fk_swb_staff FOREIGN KEY (staff_id) REFERENCES users(id), "
            "CONSTRAINT fk_swb_store FOREIGN KEY (store_id) REFERENCES merchant_stores(id)"
            ")"
        ))

    # 5. order_notes 表
    if table_cols.get("order_notes") is None:
        await conn.execute(text(
            "CREATE TABLE order_notes ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "order_id INT NOT NULL, "
            "store_id INT NOT NULL, "
            "staff_user_id INT NOT NULL, "
            "content TEXT NOT NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "INDEX ix_on_order_id (order_id), "
            "INDEX ix_on_store_id (store_id), "
            "CONSTRAINT fk_on_order FOREIGN KEY (order_id) REFERENCES unified_orders(id), "
            "CONSTRAINT fk_on_store FOREIGN KEY (store_id) REFERENCES merchant_stores(id), "
            "CONSTRAINT fk_on_staff FOREIGN KEY (staff_user_id) REFERENCES users(id)"
            ")"
        ))

    # 6. order_appointment_logs 表
    if table_cols.get("order_appointment_logs") is None:
        await conn.execute(text(
            "CREATE TABLE order_appointment_logs ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "order_item_id INT NOT NULL, "
            "old_appointment_time VARCHAR(200) NULL, "
            "new_appointment_time VARCHAR(200) NOT NULL, "
            "changed_by_user_id INT NOT NULL, "
            "reason VARCHAR(500) NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "INDEX ix_oal_order_item_id (order_item_id), "
            "CONSTRAINT fk_oal_oi FOREIGN KEY (order_item_id) REFERENCES order_items(id), "
            "CONSTRAINT fk_oal_user FOREIGN KEY (changed_by_user_id) REFERENCES users(id)"
            ")"
        ))


async def _migrate_store_codes(conn: AsyncConnection) -> None:
    """[2026-04-29] 将存量 merchant_stores 的 store_code 统一迁移为 MD00001 格式。
    按 created_at ASC 顺序依次分配编号。已全部为 MD 格式时跳过。
    """
    import re

    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "merchant_stores" not in tables:
            return False
        return True

    has_table = await conn.run_sync(_load)
    if not has_table:
        return

    # 检查是否已迁移：所有 store_code 都匹配 MD\d{5} 格式则跳过
    all_codes_res = await conn.execute(text("SELECT store_code FROM merchant_stores"))
    all_codes = [row[0] for row in all_codes_res.fetchall()]
    if not all_codes:
        return
    md_pattern = re.compile(r"^MD\d{5}$")
    if all(md_pattern.match(code or "") for code in all_codes):
        return

    # 按 created_at ASC 排序，依次分配 MD00001, MD00002, ...
    rows = await conn.execute(
        text("SELECT id FROM merchant_stores ORDER BY created_at ASC, id ASC")
    )
    store_ids = [row[0] for row in rows.fetchall()]
    for idx, store_id in enumerate(store_ids, start=1):
        new_code = f"MD{idx:05d}"
        await conn.execute(
            text("UPDATE merchant_stores SET store_code = :code WHERE id = :sid"),
            {"code": new_code, "sid": store_id},
        )


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
    await _sync_merchant_v1_backend(conn)
    await _sync_settlement_proof_schema(conn)
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
    await _sync_home_tables(conn)
    await _sync_search_tables(conn)
    await _sync_notice_table(conn)
    await _sync_bottom_nav_table(conn)
    await _sync_cos_config_fields(conn)
    await _sync_drug_identify_family_member(conn)
    await _sync_chat_share_records_table(conn)
    await _sync_product_system_tables(conn)
    await _sync_tcm_configs_table(conn)
    await _sync_chat_function_button_fields(conn)
    await _sync_tcm_diagnosis_fields(conn)
    await _sync_chat_message_metadata(conn)
    await _sync_store_bindding_tables(conn)
    await _sync_card_face_fields(conn)
    await _sync_orders_status_v2(conn)
    await _migrate_store_codes(conn)
    await run_all_migrations(conn)

    columns, indexes, unique_constraints = await conn.run_sync(load_user_schema)

    if "chat_font_size" not in columns:
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN chat_font_size VARCHAR(20) DEFAULT 'standard'"
        ))

    if "wechat_openid" not in columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN wechat_openid VARCHAR(100) NULL"))
    if "apple_id" not in columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN apple_id VARCHAR(100) NULL"))
    if "member_card_no" not in columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN member_card_no VARCHAR(50) NULL"))
    if "member_card_no_old" not in columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN member_card_no_old VARCHAR(64) NULL"))
    if "user_no" not in columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN user_no VARCHAR(8) NULL"))
    if "referrer_no" not in columns:
        await conn.execute(text("ALTER TABLE users ADD COLUMN referrer_no VARCHAR(8) NULL"))

    unique_names = indexes | unique_constraints
    if "uq_users_wechat_openid" not in unique_names:
        await conn.execute(text("CREATE UNIQUE INDEX uq_users_wechat_openid ON users (wechat_openid)"))
    if "uq_users_apple_id" not in unique_names:
        await conn.execute(text("CREATE UNIQUE INDEX uq_users_apple_id ON users (apple_id)"))
    if "uq_users_member_card_no" not in unique_names:
        await conn.execute(text("CREATE UNIQUE INDEX uq_users_member_card_no ON users (member_card_no)"))
    if "ix_users_member_card_no" not in indexes:
        await conn.execute(text("CREATE INDEX ix_users_member_card_no ON users (member_card_no)"))
    if "uq_users_user_no" not in unique_names:
        await conn.execute(text("CREATE UNIQUE INDEX uq_users_user_no ON users (user_no)"))
    if "ix_users_user_no" not in indexes:
        await conn.execute(text("CREATE INDEX ix_users_user_no ON users (user_no)"))
    if "ix_users_referrer_no" not in indexes:
        await conn.execute(text("CREATE INDEX ix_users_referrer_no ON users (referrer_no)"))
