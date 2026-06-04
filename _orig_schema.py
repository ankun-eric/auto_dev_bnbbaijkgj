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
        tables = set(inspector.get_table_names())
        if "prompt_templates" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("prompt_templates")}

    columns = await conn.run_sync(_load)
    if columns is None:
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
            "code VARCHAR(64) NULL, "
            "is_builtin BOOLEAN NOT NULL DEFAULT FALSE, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ")"
        ))
    else:
        # [PRD-AICHAT-CAPSULE-V2 2026-05-15] 澧為噺琛ュ瓧娈碉細code + is_builtin
        if "code" not in columns:
            await conn.execute(text(
                "ALTER TABLE prompt_templates ADD COLUMN code VARCHAR(64) NULL"
            ))
        if "is_builtin" not in columns:
            await conn.execute(text(
                "ALTER TABLE prompt_templates ADD COLUMN is_builtin BOOLEAN NOT NULL DEFAULT FALSE"
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
            await conn.execute(text("ALTER TABLE asr_configs ADD COLUMN supported_dialects VARCHAR(200) DEFAULT '鏅€氳瘽,绮よ'"))


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
    """[2026-04-25] 鍟嗗涓汉淇℃伅鍥炲～ + H5 搴楅摵淇℃伅鍙紪杈?
    - users 琛ㄦ柊澧?last_login_at 瀛楁锛岀敤浜庝釜浜轰俊鎭〉"鏈€杩戠櫥褰?灞曠ず
    - merchant_stores 琛ㄦ柊澧?logo_url / description / business_hours / license_no / legal_person
      瀛楁锛岀敤浜?H5 搴楅摵淇℃伅缂栬緫椤?    """
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
            "DEFAULT '璇风‘淇濊嵂鍝佸悕绉般€佸搧鐗屻€佽鏍煎畬鏁达紝鎷嶆憚娓呮櫚'"
        ))
    if "max_photo_count" not in columns:
        await conn.execute(text(
            "ALTER TABLE chat_function_buttons ADD COLUMN max_photo_count INT NULL DEFAULT 5"
        ))
    # [PRD-AICHAT-HOME-GRID-V1 2026-05-16] 鏂板涓や釜鐙珛寮€鍏冲瓧娈碉細is_recommended / is_capsule
    if "is_recommended" not in columns:
        await conn.execute(text(
            "ALTER TABLE chat_function_buttons ADD COLUMN is_recommended TINYINT(1) NULL DEFAULT 0"
        ))
    if "is_capsule" not in columns:
        await conn.execute(text(
            "ALTER TABLE chat_function_buttons ADD COLUMN is_capsule TINYINT(1) NULL DEFAULT 0"
        ))
    # [PRD-AICHAT-FUNCBTN-OPTIM-V1 2026-05-17] 5 涓柊瀛楁锛堝箓绛夛級
    if "grid_sort" not in columns:
        await conn.execute(text(
            "ALTER TABLE chat_function_buttons ADD COLUMN grid_sort INT NULL DEFAULT 0"
        ))
    if "capsule_sort" not in columns:
        await conn.execute(text(
            "ALTER TABLE chat_function_buttons ADD COLUMN capsule_sort INT NULL DEFAULT 0"
        ))
    if "ai_function_type" not in columns:
        await conn.execute(text(
            "ALTER TABLE chat_function_buttons ADD COLUMN ai_function_type VARCHAR(40) NULL"
        ))
    if "ai_opening" not in columns:
        await conn.execute(text(
            "ALTER TABLE chat_function_buttons ADD COLUMN ai_opening TEXT NULL"
        ))
    if "pre_card_for_navigate" not in columns:
        await conn.execute(text(
            "ALTER TABLE chat_function_buttons ADD COLUMN pre_card_for_navigate TINYINT(1) NULL DEFAULT 0"
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
        # [璁㈠崟鏍搁攢鐮佺姸鎬佷笌鏈敮浠樿秴鏃舵不鐞?v1.0] 鍒犻櫎鍟嗗搧缁村害 payment_timeout_minutes
        # 鍏ㄥ眬鏀粯瓒呮椂鏀圭敱 settings.PAYMENT_TIMEOUT_MINUTES 鎺у埗锛堥粯璁?15 鍒嗛挓锛?        if "payment_timeout_minutes" in cols:
            try:
                await conn.execute(text("ALTER TABLE products DROP COLUMN payment_timeout_minutes"))
            except Exception:
                pass
        if "purchase_appointment_mode" not in cols:
            await conn.execute(text(
                "ALTER TABLE products ADD COLUMN purchase_appointment_mode "
                "ENUM('purchase_with_appointment','appointment_later','must_appoint','appoint_later') NULL"
            ))
        else:
            # 鏋氫妇鎵╁锛氬吋瀹规柊鏃т袱濂楀€硷紙BUG-PRODUCT-APPT-001锛?            try:
                await conn.execute(text(
                    "ALTER TABLE products MODIFY COLUMN purchase_appointment_mode "
                    "ENUM('purchase_with_appointment','appointment_later','must_appoint','appoint_later') NULL"
                ))
            except Exception:
                pass
        # 鈹€鈹€ 棰勭害鑱斿姩 UI 鏂板瀛楁锛圔UG-PRODUCT-APPT-001锛夆攢鈹€
        if "advance_days" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN advance_days INT NULL"))
        if "daily_quota" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN daily_quota INT NULL"))
        if "time_slots" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN time_slots JSON NULL"))
        # 鈹€鈹€ BUG-PRODUCT-APPT-002锛歩nclude_today 瀛楁锛坉ate / time_slot 鍏辩敤锛岄粯璁?true锛夆攢鈹€
        if "include_today" not in cols:
            await conn.execute(text(
                "ALTER TABLE products ADD COLUMN include_today TINYINT(1) NOT NULL DEFAULT 1 "
                "COMMENT '棰勭害璧峰鏃ユ槸鍚﹀寘鍚粖澶╋紝榛樿 true'"
            ))
        # 鈹€鈹€ 鍘嗗彶鏁版嵁鍏滃簳锛堝箓绛夛級锛歵ime_slot 妯″紡 advance_days 涓虹┖ 鈫?7 澶?鈹€鈹€
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
        # 鈹€鈹€ 棰勭害妯″紡鏋氫妇瀵归綈锛歁ySQL ENUM 鎵╁ + 鏃у€兼竻娲楋紙BUG-PRODUCT-APPT-001锛夆攢鈹€
        try:
            await conn.execute(text(
                "ALTER TABLE products MODIFY COLUMN appointment_mode "
                "ENUM('none','date','time_slot','custom_form','schedule','free_time','walk_in') "
                "NOT NULL DEFAULT 'none'"
            ))
        except Exception:
            pass
        # 灏嗚繃鏈熺殑鏃у€奸噸鍐欎负 none锛岄伩鍏?ORM LookupError
        try:
            await conn.execute(text(
                "UPDATE products SET appointment_mode = 'none' "
                "WHERE appointment_mode IN ('schedule','free_time','walk_in')"
            ))
        except Exception:
            pass
        # 鏈€缁堝啀娆℃敹缂╀负鐩爣鏋氫妇
        try:
            await conn.execute(text(
                "ALTER TABLE products MODIFY COLUMN appointment_mode "
                "ENUM('none','date','time_slot','custom_form') NOT NULL DEFAULT 'none'"
            ))
        except Exception:
            pass
        # 鈹€鈹€ 鍟嗗搧寮圭獥浼樺寲 v2 鏂板瀛楁 鈹€鈹€
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
        # 鈹€鈹€ 鍟嗗搧鍔熻兘浼樺寲 v1.0锛氳惀閿€瑙掓爣锛坙imited/hot/new/recommend锛?鈹€鈹€
        if "marketing_badges" not in cols:
            await conn.execute(text("ALTER TABLE products ADD COLUMN marketing_badges JSON NULL"))
        # 鈹€鈹€ 鍟嗗搧鍔熻兘浼樺寲 v1.0锛氬交搴曟竻鐞嗘湁鏁堟棩鏈熷瓧娈碉紙鐢ㄦ埛閫夋嫨 C. 褰诲簳娓呯┖锛?鈹€鈹€
        # 骞傜瓑鎵ц锛氬垪瀛樺湪鍒?DROP锛涗笉瀛樺湪鍒欒烦杩囥€傛墍鏈夊紓甯搁潤榛樺鐞嗭紙渚嬪 MySQL 涓嶅悓鐗堟湰鐨勮娉曞樊寮傦級
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

    # 鈹€鈹€ 棰勭害琛ㄥ崟搴擄細涓?appointment_forms 澧炲姞 status 鍒楋紙BUG-PRODUCT-APPT-001锛夆攢鈹€
    if "appointment_forms" in table_cols:
        af_cols = table_cols["appointment_forms"]
        if "status" not in af_cols:
            await conn.execute(text(
                "ALTER TABLE appointment_forms ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"
            ))

    # 鍒涘缓 product_skus 琛紙濡傛灉涓嶅瓨鍦級
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
        # [璁㈠崟鏍搁攢鐮佺姸鎬佷笌鏈敮浠樿秴鏃舵不鐞?v1.0]
        # 鍒犻櫎璁㈠崟缁村害 payment_timeout_minutes锛堝巻鍙插揩鐓у€间涪寮冿級
        # 鍏ㄥ眬鏀粯瓒呮椂鏀圭敱 settings.PAYMENT_TIMEOUT_MINUTES 鎺у埗
        if "payment_timeout_minutes" in cols:
            try:
                await conn.execute(text("ALTER TABLE unified_orders DROP COLUMN payment_timeout_minutes"))
            except Exception:
                pass
        # 鍒犻櫎 order_timeout_minutes锛堝鏋滃巻鍙叉暟鎹簱涓瓨鍦級锛岃矾寰?3銆岄棬搴楄秴鏃舵湭纭鑷姩鍙栨秷銆嶅凡涓嬬嚎
        if "order_timeout_minutes" in cols:
            try:
                await conn.execute(text("ALTER TABLE unified_orders DROP COLUMN order_timeout_minutes"))
            except Exception:
                pass
        if "has_reviewed" not in cols:
            await conn.execute(text("ALTER TABLE unified_orders ADD COLUMN has_reviewed BOOLEAN DEFAULT FALSE"))
        # [PRD-01 鍏ㄥ钩鍙板浐瀹氭椂娈靛垏鐗囦綋绯?v1.0 路 F-01-3] time_slot 娈靛彿 1-9
        if "time_slot" not in cols:
            await conn.execute(text(
                "ALTER TABLE unified_orders ADD COLUMN time_slot INT NULL "
                "COMMENT '鍥哄畾 9 娈垫椂娈垫鍙凤紙1-9锛夛紝鍑屾櫒娈?鏃犻绾︽椂闂翠负 NULL'"
            ))
            try:
                await conn.execute(text(
                    "CREATE INDEX ix_unified_orders_time_slot ON unified_orders(time_slot)"
                ))
            except Exception:
                pass

    # [璁㈠崟鏍搁攢鐮佺姸鎬佷笌鏈敮浠樿秴鏃舵不鐞?v1.0] 鍘嗗彶鑴忔暟鎹竴娆℃€ф竻娲楋細
    # 鎵惧埌鎵€鏈夈€寀nified_orders.status = cancelled 涓斿叾涓嬩换鎰?order_items.redemption_code_status = active銆?    # 鐨勮褰曪紝鎶婃牳閿€鐮佸叏閮ㄥ埛涓?expired銆?    # 骞傜瓑锛氶噸澶嶆墽琛屼笉浼氭敼鍐欏凡涓?expired/redeemed/refunded/used/locked 鐨勬牳閿€鐮併€?    if "unified_orders" in table_cols and "order_items" in table_cols:
        try:
            await conn.execute(text(
                "UPDATE order_items oi "
                "JOIN unified_orders uo ON uo.id = oi.order_id "
                "SET oi.redemption_code_status = 'expired', oi.updated_at = CURRENT_TIMESTAMP "
                "WHERE uo.status = 'cancelled' AND oi.redemption_code_status = 'active'"
            ))
        except Exception:
            # 閮ㄥ垎鏁版嵁搴擄紙濡?SQLite 娴嬭瘯鐜锛変笉鏀寔 UPDATE...JOIN 璇硶锛?            # 鏀圭敤瀛愭煡璇㈠厹搴曪紙鐢熶骇鐜 MySQL 璧颁笂闈㈢殑蹇矾寰勶級
            try:
                await conn.execute(text(
                    "UPDATE order_items SET redemption_code_status = 'expired', "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE redemption_code_status = 'active' "
                    "AND order_id IN (SELECT id FROM unified_orders WHERE status = 'cancelled')"
                ))
            except Exception:
                pass

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
    """v1 鍟嗗鍚庡彴 + 鏈烘瀯浣撶郴锛?    - MerchantMemberRole 鎵╁睍 ENUM: owner/staff/store_manager/verifier/finance
    - merchant_profiles 鏂板 category_id
    - 鍏朵粬鏂拌〃鐢?metadata.create_all 鑷姩鍒涘缓
    - 鍒濆鍖栭粯璁?merchant_categories
    [2026-04-24] 鎵╁睍锛?    - merchant_stores 鏂板 category_id
    - merchant_store_memberships 鏂板 role_code
    - 鏂板 merchant_role_templates 琛?+ 4 鏉￠粯璁よ鑹?    - 瀛橀噺 membership 鑷姩鍥炲～ role_code
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

    # ENUM 鎵╁睍锛圡ySQL锛歁ODIFY COLUMN 涓烘柊 ENUM锛?    if "merchant_store_memberships" in tables:
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

    # [2026-04-24] merchant_stores 鏂板 category_id
    if ms_cols is not None and "category_id" not in ms_cols:
        try:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN category_id INT NULL"))
            await conn.execute(text("CREATE INDEX ix_ms_category ON merchant_stores(category_id)"))
        except Exception:
            pass

    # [2026-04-24] merchant_store_memberships 鏂板 role_code
    if mem_cols is not None and "role_code" not in mem_cols:
        try:
            await conn.execute(text("ALTER TABLE merchant_store_memberships ADD COLUMN role_code VARCHAR(32) NULL"))
            await conn.execute(text("CREATE INDEX ix_mem_role_code ON merchant_store_memberships(role_code)"))
        except Exception:
            pass

    # 榛樿鏈烘瀯绫诲埆锛堝箓绛夛級
    if "merchant_categories" in tables:
        default_cats = [
            ("self_store", "鑷惀闂ㄥ簵", "馃彧", ["image", "pdf"], "闄勪欢", 10),
            ("medical", "浣撴鏈烘瀯", "馃彞", ["image", "pdf"], "妫€鏌ユ姤鍛?, 20),
            ("homeservice", "瀹舵斂鏈烘瀯", "馃Ч", ["image", "pdf"], "鏈嶅姟宸ュ崟", 30),
            ("other", "鍏朵粬鏈烘瀯", "馃彿锔?, ["image", "pdf"], "闄勪欢", 99),
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

    # [2026-04-24] 榛樿瑙掕壊妯℃澘锛堝箓绛夋彃鍏?+ 鍥炲～瀛橀噺 membership锛?    # 閲嶆柊璇诲彇 tables 浠ュ寘鍚柊鍒涘缓鐨?merchant_role_templates
    def _tables_only(sync_conn):
        return set(inspect(sync_conn).get_table_names())
    tables2 = await conn.run_sync(_tables_only)
    if "merchant_role_templates" in tables2:
        import json as _json
        # 8 妯″潡浣撶郴锛堜笌 admin_merchant.FULL_MODULE_CODES 淇濇寔涓€鑷达級
        default_roles = [
            ("boss", "鑰佹澘", ["dashboard", "verify", "records", "messages", "profile", "finance", "staff", "settings"], 10),
            ("manager", "搴楅暱", ["dashboard", "verify", "records", "messages", "profile", "finance", "staff", "settings"], 20),
            ("finance", "璐㈠姟", ["dashboard", "records", "messages", "profile", "finance"], 30),
            ("clerk", "搴楀憳", ["dashboard", "verify", "records", "messages", "profile"], 40),
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

        # 鍥炲～ membership.role_code锛歰wner->boss锛屽叾瀹?>clerk锛堜笉瑕嗙洊宸叉湁鍊硷級
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
    """[2026-04-24] 瀵硅处鍗曞嚟璇佹墿灞曪細鏂板 voucher_type / voucher_files / remark / updated_at 鍒楋紱
    file_url 鏀惧涓哄彲绌猴紙浠ユ敮鎸佹柊妯″紡鍙瓨 voucher_files 鑰屼笉瀛樺崟涓€ file_url锛夈€?    """
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
    """[2026-05-03 鍗＄鐞?PRD v1.1] card_definitions 鏂板鍗￠潰璁剧疆 4 瀛楁銆?    澧為噺銆佸箓绛夈€傝€佹暟鎹寜榛樿鍊煎洖濉€?    """
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
            "COMMENT '鍗￠潰鏍峰紡 ST1~ST4'"
        ))
    if "face_bg_code" not in columns:
        await conn.execute(text(
            "ALTER TABLE card_definitions ADD COLUMN face_bg_code VARCHAR(8) NOT NULL DEFAULT 'BG1' "
            "COMMENT '鍗￠潰鑳屾櫙 BG1~BG8'"
        ))
    if "face_show_flags" not in columns:
        await conn.execute(text(
            "ALTER TABLE card_definitions ADD COLUMN face_show_flags INT NOT NULL DEFAULT 7 "
            "COMMENT '4 椤规樉绀轰綅 bitmask锛涢粯璁?7=SH1+SH2+SH3'"
        ))
    if "face_layout" not in columns:
        await conn.execute(text(
            "ALTER TABLE card_definitions ADD COLUMN face_layout VARCHAR(8) NOT NULL DEFAULT 'ON_CARD' "
            "COMMENT '淇℃伅甯冨眬锛屾湰鏈熷浐瀹?ON_CARD'"
        ))


async def _sync_cards_v2_fields(conn: AsyncConnection) -> None:
    """[2026-05-03 鍗＄鐞?v2.0 绗?2~5 鏈焆
    1) unified_orders 鏂板 product_type / card_definition_id / items_snapshot / split_group_id /
       renew_from_user_card_id
    2) user_cards 鏂板 renewed_from_id / renew_count
    3) card_usage_logs 鏂板 merchant_id
    4) 鏂板缓 card_redemption_codes 琛紙SQLite/MySQL 鑷姩寤猴級
    鍏ㄩ儴澧為噺銆佸箓绛夈€?    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        out = {
            "unified_orders": None,
            "user_cards": None,
            "card_usage_logs": None,
            "card_redemption_codes_exists": "card_redemption_codes" in tables,
        }
        if "unified_orders" in tables:
            out["unified_orders"] = {col["name"] for col in inspector.get_columns("unified_orders")}
        if "user_cards" in tables:
            out["user_cards"] = {col["name"] for col in inspector.get_columns("user_cards")}
        if "card_usage_logs" in tables:
            out["card_usage_logs"] = {col["name"] for col in inspector.get_columns("card_usage_logs")}
        return out

    info = await conn.run_sync(_load)
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = ""

    # 鈹€鈹€ 1) unified_orders 鍔犲垪 鈹€鈹€
    uo_cols = info.get("unified_orders")
    if uo_cols is not None:
        if "product_type" not in uo_cols:
            await conn.execute(text(
                "ALTER TABLE unified_orders ADD COLUMN product_type VARCHAR(20) NOT NULL DEFAULT 'physical'"
            ))
            try:
                await conn.execute(text(
                    "CREATE INDEX ix_unified_orders_product_type ON unified_orders(product_type)"
                ))
            except Exception:
                pass
        if "card_definition_id" not in uo_cols:
            await conn.execute(text(
                "ALTER TABLE unified_orders ADD COLUMN card_definition_id INT NULL"
            ))
            try:
                await conn.execute(text(
                    "CREATE INDEX ix_unified_orders_card_definition_id ON unified_orders(card_definition_id)"
                ))
            except Exception:
                pass
        if "items_snapshot" not in uo_cols:
            # MySQL: JSON 绫诲瀷锛汼QLite: 鐢?TEXT 鍏煎
            col_type = "JSON" if dialect_name == "mysql" else "TEXT"
            await conn.execute(text(
                f"ALTER TABLE unified_orders ADD COLUMN items_snapshot {col_type} NULL"
            ))
        if "split_group_id" not in uo_cols:
            await conn.execute(text(
                "ALTER TABLE unified_orders ADD COLUMN split_group_id VARCHAR(32) NULL"
            ))
            try:
                await conn.execute(text(
                    "CREATE INDEX ix_unified_orders_split_group_id ON unified_orders(split_group_id)"
                ))
            except Exception:
                pass
        if "renew_from_user_card_id" not in uo_cols:
            await conn.execute(text(
                "ALTER TABLE unified_orders ADD COLUMN renew_from_user_card_id INT NULL"
            ))

    # 鈹€鈹€ 2) user_cards 鍔犲垪 鈹€鈹€
    uc_cols = info.get("user_cards")
    if uc_cols is not None:
        if "renewed_from_id" not in uc_cols:
            await conn.execute(text(
                "ALTER TABLE user_cards ADD COLUMN renewed_from_id INT NULL"
            ))
            try:
                await conn.execute(text(
                    "CREATE INDEX ix_user_cards_renewed_from_id ON user_cards(renewed_from_id)"
                ))
            except Exception:
                pass
        if "renew_count" not in uc_cols:
            await conn.execute(text(
                "ALTER TABLE user_cards ADD COLUMN renew_count INT NOT NULL DEFAULT 0"
            ))

    # 鈹€鈹€ 3) card_usage_logs 鍔犲垪 鈹€鈹€
    cul_cols = info.get("card_usage_logs")
    if cul_cols is not None:
        if "merchant_id" not in cul_cols:
            await conn.execute(text(
                "ALTER TABLE card_usage_logs ADD COLUMN merchant_id INT NULL"
            ))
            try:
                await conn.execute(text(
                    "CREATE INDEX ix_card_usage_logs_merchant_id ON card_usage_logs(merchant_id)"
                ))
            except Exception:
                pass

    # 鈹€鈹€ 3.5) card_definitions.renew_strategy ENUM 鎵╁€硷紙add_on/new_card 鈫?+STACK/RESET/DISABLED锛夆攢鈹€
    if dialect_name == "mysql":
        try:
            await conn.execute(text(
                "ALTER TABLE card_definitions MODIFY COLUMN renew_strategy "
                "ENUM('add_on','new_card','STACK','RESET','DISABLED') NOT NULL DEFAULT 'add_on'"
            ))
        except Exception:
            pass

    # 鈹€鈹€ 4) card_redemption_codes 琛?鈹€鈹€锛圫QLAlchemy create_all 閫氬父浼氬缓锛岃繖閲屽厹搴曪級
    if not info.get("card_redemption_codes_exists"):
        if dialect_name == "mysql":
            await conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS card_redemption_codes (
                    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    user_card_id INT NOT NULL,
                    code_token VARCHAR(64) NOT NULL UNIQUE,
                    code_digits VARCHAR(6) NOT NULL,
                    issued_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL,
                    status VARCHAR(16) NOT NULL DEFAULT 'active',
                    used_at DATETIME NULL,
                    used_by_log_id INT NULL,
                    created_at DATETIME NULL,
                    INDEX ix_crc_user_card_id (user_card_id),
                    INDEX ix_crc_status (status),
                    INDEX ix_crc_expires_at (expires_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            ))
        else:
            # SQLite create_all 鍏滃簳锛堝鏁版儏鍐靛凡寤哄ソ锛?            await conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS card_redemption_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_card_id INTEGER NOT NULL,
                    code_token VARCHAR(64) NOT NULL UNIQUE,
                    code_digits VARCHAR(6) NOT NULL,
                    issued_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL,
                    status VARCHAR(16) NOT NULL DEFAULT 'active',
                    used_at DATETIME,
                    used_by_log_id INTEGER,
                    created_at DATETIME
                )
                """
            ))


async def _sync_orders_status_v2(conn: AsyncConnection) -> None:
    """[2026-05-03 PRD V2 鏍搁攢璁㈠崟鐘舵€佷綋绯讳紭鍖朷
    1) order_items 鏂板 redemption_code_status / redemption_code_expires_at
    2) unified_orders.status ENUM 鎵╁垪鍒?12 鍊硷紙淇濈暀 pending_review 鍏煎锛?    3) 涓€娆℃€ф暟鎹縼绉伙紙鐢?system_configs 鏍囪鐗堟湰鍙凤紝骞傜瓑锛夛細
       - pending_review 鈫?completed锛圴2 鍙栨秷"寰呰瘎浠?鐙珛鐘舵€侊級
       - 寰呮牳閿€ + 宸茶繃鏈燂細pending_use 涓?redemption_code_expires_at 宸茶繃 鈫?expired
       - 閫€娆捐瀺鍚堬細refund_status=refund_success 涓?status!=cancelled 鈫?refunded
                  refund_status=applied/reviewing/returning 涓?status!=cancelled 鈫?refunding
    鎵€鏈夋搷浣滃潎涓?try/except + warn锛岀己瀛楁鏃惰烦杩囪鏉¤鍒欍€?    """
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

    # 鈹€鈹€ 1) order_items 鍔犲垪 鈹€鈹€
    if table_cols.get("order_items") is not None:
        cols = table_cols["order_items"]
        if "redemption_code_status" not in cols:
            await conn.execute(text(
                "ALTER TABLE order_items ADD COLUMN redemption_code_status "
                "VARCHAR(16) NOT NULL DEFAULT 'active' "
                "COMMENT '鏍搁攢鐮?5 鎬侊細active/locked/used/expired/refunded锛圥RD V2锛?"
            ))
            await conn.execute(text(
                "CREATE INDEX ix_order_items_redemption_code_status "
                "ON order_items(redemption_code_status)"
            ))
        if "redemption_code_expires_at" not in cols:
            await conn.execute(text(
                "ALTER TABLE order_items ADD COLUMN redemption_code_expires_at "
                "DATETIME NULL COMMENT '鏍搁攢鐮佽繃鏈熸椂闂达紙PRD V2锛?"
            ))

    # 鈹€鈹€ 2) unified_orders.status ENUM 鎵╁垪 鈹€鈹€
    if table_cols.get("unified_orders") is not None:
        # MySQL锛歁ODIFY ENUM 鎶婃墍鏈?12 + 1锛坧ending_review 鍏煎锛夋灇涓惧€煎垪鍑?        # 鍦?SQLite 涓嬩笉瀛樺湪 ENUM 姒傚康锛孶nifiedOrderStatus 鐨?String 姣旇緝浠嶈兘宸ヤ綔锛?        # 涓哄吋瀹规€ф澶勪粎鍦?MySQL 鏂硅█涓嬫墽琛屻€?        try:
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
                # 鍗充娇 ALTER 澶辫触锛堝凡缁忔槸鏇村鐨勬灇涓撅級锛屼篃鍏佽缁х画
                print(f"[schema_sync] _sync_orders_status_v2 ALTER status enum warn: {e}")

    # 鈹€鈹€ 3) 涓€娆℃€ф暟鎹縼绉伙細鐗堟湰鍙峰啓鍏?system_configs 鈹€鈹€
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
            # system_configs 鍒楀悕鍙兘涓嶅悓锛涘皾璇曞閫?            try:
                row = (await conn.execute(text(
                    "SELECT value FROM system_configs WHERE `key` = :k"
                ), {"k": MIGRATION_KEY})).fetchone()
                if row and (row[0] == MIGRATION_VAL):
                    already_migrated = True
            except Exception:
                already_migrated = False

    if already_migrated:
        return

    # 鐪熸鎵ц杩佺Щ
    if table_cols.get("unified_orders") is None:
        return  # 娌℃湁璇ヨ〃锛屾暣浣撹烦杩?
    uo_cols = table_cols["unified_orders"]

    # 瑙勫垯 1锛歱ending_review 鈫?completed
    try:
        r = await conn.execute(text(
            "UPDATE unified_orders SET status='completed' "
            "WHERE status='pending_review'"
        ))
        print(f"[orders_v2 migrate] pending_review鈫抍ompleted rows={r.rowcount}")
    except Exception as e:
        print(f"[orders_v2 migrate] pending_review鈫抍ompleted skip: {e}")

    # 瑙勫垯 2锛歳efund_status=refund_success 涓?status!=cancelled 鈫?refunded
    if "refund_status" in uo_cols:
        try:
            r = await conn.execute(text(
                "UPDATE unified_orders SET status='refunded' "
                "WHERE refund_status='refund_success' AND status<>'cancelled' "
                "AND status<>'refunded'"
            ))
            print(f"[orders_v2 migrate] refund_success鈫抮efunded rows={r.rowcount}")
        except Exception as e:
            print(f"[orders_v2 migrate] refund_success鈫抮efunded skip: {e}")

        # 瑙勫垯 3锛歳efund_status in (applied/reviewing/returning) 鈫?refunding
        try:
            r = await conn.execute(text(
                "UPDATE unified_orders SET status='refunding' "
                "WHERE refund_status IN ('applied','reviewing','returning') "
                "AND status NOT IN ('cancelled','refunded','refunding')"
            ))
            print(f"[orders_v2 migrate] refund_in_progress鈫抮efunding rows={r.rowcount}")
        except Exception as e:
            print(f"[orders_v2 migrate] refund_in_progress鈫抮efunding skip: {e}")

    # 瑙勫垯 4锛歱ending_use + redemption_code_expires_at 杩囨湡 鈫?expired
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
            print(f"[orders_v2 migrate] pending_use_expired鈫抏xpired rows={r.rowcount}")
        except Exception as e:
            print(f"[orders_v2 migrate] pending_use_expired鈫抏xpired skip: {e}")

    # 鍐欏叆鐗堟湰鍙凤紙宸茶縼绉伙級
    if has_sysconf:
        try:
            await conn.execute(text(
                "INSERT INTO system_configs (config_key, config_value, description, created_at, updated_at) "
                "VALUES (:k, :v, 'orders_status_v2 migration done', NOW(), NOW()) "
                "ON DUPLICATE KEY UPDATE config_value=:v, updated_at=NOW()"
            ), {"k": MIGRATION_KEY, "v": MIGRATION_VAL})
        except Exception as e:
            # SQLite 涓嶆敮鎸?ON DUPLICATE KEY锛涘仛涓€娆℃櫘閫氱殑 INSERT OR REPLACE
            try:
                await conn.execute(text(
                    "INSERT OR REPLACE INTO system_configs (config_key, config_value) "
                    "VALUES (:k, :v)"
                ), {"k": MIGRATION_KEY, "v": MIGRATION_VAL})
            except Exception as e2:
                print(f"[orders_v2 migrate] write version flag skip: {e}/{e2}")


async def _sync_store_bindding_tables(conn: AsyncConnection) -> None:
    """闂ㄥ簵缁戝畾涓庤鍗曢€氱煡澧炲己锛氭柊澧炲瓧娈典笌琛ㄣ€?""
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

    # 1. merchant_stores 鏂板 business_scope
    if table_cols.get("merchant_stores") is not None:
        cols = table_cols["merchant_stores"]
        if "business_scope" not in cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN business_scope JSON NULL"))
        if "lat" not in cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN lat DECIMAL(10,6) NULL"))
        if "lng" not in cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN lng DECIMAL(10,6) NULL"))
        # [2026-05-01 闂ㄥ簵鍦板浘鑳藉姏 PRD v1.0] 鐪?甯?鍖烘媶鍒嗗瓧娈?        if "province" not in cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN province VARCHAR(50) NULL"))
        if "city" not in cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN city VARCHAR(50) NULL"))
        if "district" not in cols:
            await conn.execute(text("ALTER TABLE merchant_stores ADD COLUMN district VARCHAR(50) NULL"))
        # [2026-05-02 H5 涓嬪崟娴佺▼浼樺寲 PRD v1.0] 鍗曟椂娈垫渶澶ф帴鍗曟暟 + 钀ヤ笟璧锋鏃堕棿
        if "slot_capacity" not in cols:
            await conn.execute(text(
                "ALTER TABLE merchant_stores ADD COLUMN slot_capacity INT NOT NULL DEFAULT 10 "
                "COMMENT '鍗曟椂娈垫渶澶ф帴鍗曟暟锛岄粯璁?10'"
            ))
        if "business_start" not in cols:
            await conn.execute(text(
                "ALTER TABLE merchant_stores ADD COLUMN business_start VARCHAR(5) NULL "
                "COMMENT '钀ヤ笟寮€濮?HH:MM'"
            ))
        if "business_end" not in cols:
            await conn.execute(text(
                "ALTER TABLE merchant_stores ADD COLUMN business_end VARCHAR(5) NULL "
                "COMMENT '钀ヤ笟缁撴潫 HH:MM'"
            ))

        # 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲
        # [2026-05-03 钀ヤ笟鏃堕棿/钀ヤ笟鑼冨洿淇濆瓨 Bug 淇] 涓€娆℃€ф暟鎹縼绉伙細
        # 鎶婄幇缃?business_hours 瀛楃涓茶В鏋愬洖濉埌 business_start / business_end銆?        # 瑙ｆ瀽澶辫触鐨勪繚鐣欏師鍊硷紝business_start/business_end 鐣欑┖锛岀瓑鍟嗗涓婄嚎鍚庤嚜琛岄€夊～銆?        # 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲
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
                # 浠呭尮閰嶇被浼?"09:00 - 22:00" / "09:00-22:00" / "9:00~22:00" 绛夊父瑙?ASCII 鏁板瓧鏍煎紡
                m = _re.match(
                    r"^\s*(\d{1,2}):(\d{2})\s*[-~鑷冲埌 ]+\s*(\d{1,2}):(\d{2})\s*$",
                    hours_str,
                )
                if not m:
                    skipped += 1
                    continue
                sh, sm, eh, em = (int(m.group(1)), int(m.group(2)),
                                  int(m.group(3)), int(m.group(4)))
                if not (0 <= sh <= 23 and 0 <= eh <= 23 and sm in (0, 30) and em in (0, 30)):
                    # 闈?30 鍒嗛挓鏁寸偣鐨勶紝鎸?灏辫繎 30 鍒?瀵归綈锛歮m<15鈫?0, 15鈮m<45鈫?0, mm鈮?5鈫掍笅涓皬鏃?                    def _round_30(h, m_):
                        if m_ < 15:
                            return h, 0
                        if m_ < 45:
                            return h, 30
                        return min(h + 1, 23), 0
                    sh, sm = _round_30(sh, sm)
                    eh, em = _round_30(eh, em)
                bs_str = f"{sh:02d}:{sm:02d}"
                be_str = f"{eh:02d}:{em:02d}"
                # 闄愬畾鍒?07:00鈥?2:00
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

    # 2. merchant_notifications 鏂板 notification_type
    if table_cols.get("merchant_notifications") is not None:
        cols = table_cols["merchant_notifications"]
        if "notification_type" not in cols:
            await conn.execute(text(
                "ALTER TABLE merchant_notifications ADD COLUMN notification_type VARCHAR(50) DEFAULT 'system'"
            ))

    # 3. unified_orders 鏂板 store_confirmed, store_confirmed_at, store_id
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

    # 4. staff_wechat_bindings 琛紙鐢?metadata.create_all 澶勭悊锛屾澶勫彧鍔犵己澶卞垪锛?    if table_cols.get("staff_wechat_bindings") is None:
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

    # 5. order_notes 琛?    if table_cols.get("order_notes") is None:
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

    # 6. order_appointment_logs 琛?    if table_cols.get("order_appointment_logs") is None:
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
    """[2026-04-29] 灏嗗瓨閲?merchant_stores 鐨?store_code 缁熶竴杩佺Щ涓?MD00001 鏍煎紡銆?    鎸?created_at ASC 椤哄簭渚濇鍒嗛厤缂栧彿銆傚凡鍏ㄩ儴涓?MD 鏍煎紡鏃惰烦杩囥€?    """
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

    # 妫€鏌ユ槸鍚﹀凡杩佺Щ锛氭墍鏈?store_code 閮藉尮閰?MD\d{5} 鏍煎紡鍒欒烦杩?    all_codes_res = await conn.execute(text("SELECT store_code FROM merchant_stores"))
    all_codes = [row[0] for row in all_codes_res.fetchall()]
    if not all_codes:
        return
    md_pattern = re.compile(r"^MD\d{5}$")
    if all(md_pattern.match(code or "") for code in all_codes):
        return

    # 鎸?created_at ASC 鎺掑簭锛屼緷娆″垎閰?MD00001, MD00002, ...
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


async def _sync_on_site_fulfillment(conn: AsyncConnection) -> None:
    """[涓婇棬鏈嶅姟灞ョ害 PRD v1.0] 鏂板 on_site 灞ョ害绫诲瀷 + 涓婇棬鍦板潃瀛楁銆?
    1) products.fulfillment_type ENUM 鎵╁垪锛氬鍔?'on_site'
    2) order_items.fulfillment_type ENUM 鎵╁垪锛氬鍔?'on_site'
    3) unified_orders 鏂板锛歴ervice_address_id銆乻ervice_address_snapshot

    鍏ㄩ儴澧為噺銆佸箓绛夈€備粎 MySQL 鏂硅█涓嬫墽琛?ENUM ALTER锛圫QLite 鏃?ENUM锛夈€?    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        result = {
            "products_cols": None,
            "order_items_cols": None,
            "unified_orders_cols": None,
        }
        if "products" in tables:
            result["products_cols"] = {col["name"] for col in inspector.get_columns("products")}
        if "order_items" in tables:
            result["order_items_cols"] = {col["name"] for col in inspector.get_columns("order_items")}
        if "unified_orders" in tables:
            result["unified_orders_cols"] = {col["name"] for col in inspector.get_columns("unified_orders")}
        return result

    info = await conn.run_sync(_load)
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = ""

    # 1) products.fulfillment_type 鎵?ENUM
    if info["products_cols"] is not None and dialect_name == "mysql":
        try:
            await conn.execute(text(
                "ALTER TABLE products MODIFY COLUMN fulfillment_type "
                "ENUM('in_store','delivery','virtual','on_site') NOT NULL"
            ))
        except Exception as e:
            print(f"[schema_sync] _sync_on_site_fulfillment products enum warn: {e}")

    # 2) order_items.fulfillment_type 鎵?ENUM
    if info["order_items_cols"] is not None and dialect_name == "mysql":
        try:
            await conn.execute(text(
                "ALTER TABLE order_items MODIFY COLUMN fulfillment_type "
                "ENUM('in_store','delivery','virtual','on_site') NOT NULL"
            ))
        except Exception as e:
            print(f"[schema_sync] _sync_on_site_fulfillment order_items enum warn: {e}")

    # 3) unified_orders 鏂板 service_address_id / service_address_snapshot
    if info["unified_orders_cols"] is not None:
        cols = info["unified_orders_cols"]
        if "service_address_id" not in cols:
            try:
                await conn.execute(text(
                    "ALTER TABLE unified_orders ADD COLUMN service_address_id INT NULL "
                    "COMMENT '涓婇棬鏈嶅姟鍦板潃 ID锛坲ser_addresses.id锛?"
                ))
                try:
                    await conn.execute(text(
                        "CREATE INDEX ix_unified_orders_service_address_id "
                        "ON unified_orders(service_address_id)"
                    ))
                except Exception:
                    pass
            except Exception as e:
                print(f"[schema_sync] _sync_on_site_fulfillment add service_address_id warn: {e}")
        if "service_address_snapshot" not in cols:
            col_type = "JSON" if dialect_name == "mysql" else "TEXT"
            try:
                await conn.execute(text(
                    f"ALTER TABLE unified_orders ADD COLUMN service_address_snapshot {col_type} NULL "
                    f"COMMENT '涓婇棬鍦板潃蹇収锛堜笅鍗曟椂鍒诲喕缁擄級'"
                ))
            except Exception as e:
                print(f"[schema_sync] _sync_on_site_fulfillment add service_address_snapshot warn: {e}")

    # 4) 鍙屽眰鍚嶉鏍￠獙鎵€闇€鐨勮仈鍚堢储寮曪紙鎬ц兘锛?    if info["unified_orders_cols"] is not None and dialect_name == "mysql":
        try:
            await conn.execute(text(
                "CREATE INDEX ix_unified_orders_store_status "
                "ON unified_orders(store_id, status)"
            ))
        except Exception:
            pass

    if info["order_items_cols"] is not None and dialect_name == "mysql":
        try:
            await conn.execute(text(
                "CREATE INDEX ix_order_items_product_appt "
                "ON order_items(product_id, appointment_time)"
            ))
        except Exception:
            pass


async def _migrate_redeemed_to_completed(conn: AsyncConnection) -> None:
    """[PRD 鍟嗗 PC 鍚庡彴浼樺寲 v1.1 路 F7] 涓€娆℃€ф暟鎹縼绉伙細
    鎵€鏈?status='redeemed' 鐨勮鍗曞埛涓?'completed'銆?
    鑳屾櫙锛歚redeemed` 鏄巻鍙查仐鐣欑姸鎬侊紝鏂颁唬鐮佷笉鍐嶅啓鍏ャ€傛湰杩佺Щ鎶婂瓨閲?    鐨?`redeemed` 璁㈠崟涓€娆℃€у悎骞跺埌 `completed`锛屼繚璇佸晢瀹剁 / 鐢ㄦ埛绔枃妗?    涓€鑷达紙鍧囨樉绀恒€屽凡瀹屾垚銆嶏級銆?
    骞傜瓑锛氶噸澶嶆墽琛岋紙鏃?redeemed 璁㈠崟锛夋椂涓虹┖鎿嶄綔銆?    """
    def _check_table(sync_conn):
        inspector = inspect(sync_conn)
        return "unified_orders" in set(inspector.get_table_names())

    has_table = await conn.run_sync(_check_table)
    if not has_table:
        return

    # 妫€鏌?status 瀛楁鏄惁浠嶅厑璁?'redeemed' 鍊硷紙MySQL ENUM 妫€鏌ワ級锛?    # 濡傛灉鏁版嵁搴撲腑纭疄瀛樺湪 redeemed 琛岋紝鎵ц UPDATE銆?    try:
        cnt_res = await conn.execute(
            text("SELECT COUNT(*) FROM unified_orders WHERE status = 'redeemed'")
        )
        cnt = cnt_res.scalar() or 0
    except Exception:
        # 鑻?MySQL ENUM 宸蹭笉鍐嶅寘鍚?'redeemed'锛屾煡璇細鎶ラ敊锛岃涓哄凡杩佺Щ瀹屾垚
        return

    if cnt == 0:
        return

    await conn.execute(text(
        "UPDATE unified_orders "
        "SET status = 'completed', updated_at = NOW() "
        "WHERE status = 'redeemed'"
    ))


async def _migrate_appointed_to_pending_use(conn: AsyncConnection) -> None:
    """[PRD 璁㈠崟鐘舵€佹満绠€鍖栨柟妗?v1.0 路 绗?5.4 鑺俔 涓€鍒€鍒囪縼绉伙細
    鎵€鏈?status='appointed' 鐨勮鍗曞埛涓?'pending_use'銆?
    骞傜瓑锛氶噸澶嶆墽琛岋紙鏃?appointed 璁㈠崟锛夋椂涓虹┖鎿嶄綔銆?    """
    def _check_table(sync_conn):
        inspector = inspect(sync_conn)
        return "unified_orders" in set(inspector.get_table_names())

    has_table = await conn.run_sync(_check_table)
    if not has_table:
        return

    # 鍏堢粺璁℃暟閲忥紙渚夸簬鏃ュ織璁板綍锛?    cnt_res = await conn.execute(
        text("SELECT COUNT(*) FROM unified_orders WHERE status = 'appointed'")
    )
    cnt = cnt_res.scalar() or 0
    if cnt == 0:
        return

    # 鎵ц杩佺Щ
    await conn.execute(text(
        "UPDATE unified_orders "
        "SET status = 'pending_use', updated_at = NOW() "
        "WHERE status = 'appointed'"
    ))


async def _sync_payment_config(conn: AsyncConnection) -> None:
    """[鏀粯閰嶇疆 PRD v1.0] 寤鸿〃 + 4 鏉＄瀛愯褰?+ orders/unified_orders 鍔犲垪銆?
    骞傜瓑锛氳〃宸插瓨鍦ㄦ椂鍙ˉ缂哄け鍒楋紱绉嶅瓙璁板綍宸插瓨鍦ㄦ椂鎸?channel_code 璺宠繃銆?    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        return {
            "payment_channels_exists": "payment_channels" in tables,
            "orders_cols": (
                {col["name"] for col in inspector.get_columns("orders")}
                if "orders" in tables else None
            ),
            "uo_cols": (
                {col["name"] for col in inspector.get_columns("unified_orders")}
                if "unified_orders" in tables else None
            ),
        }

    info = await conn.run_sync(_load)
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = ""

    # 鈹€鈹€ 1) payment_channels 琛?鈹€鈹€
    if not info["payment_channels_exists"]:
        if dialect_name == "mysql":
            await conn.execute(text("""
                CREATE TABLE payment_channels (
                    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    channel_code VARCHAR(32) NOT NULL UNIQUE,
                    channel_name VARCHAR(50) NOT NULL,
                    display_name VARCHAR(100) NOT NULL,
                    platform VARCHAR(20) NOT NULL,
                    provider VARCHAR(20) NOT NULL,
                    is_enabled TINYINT(1) NOT NULL DEFAULT 0,
                    is_complete TINYINT(1) NOT NULL DEFAULT 0,
                    config_json JSON NULL,
                    notify_url VARCHAR(500) NULL,
                    return_url VARCHAR(500) NULL,
                    sort_order INT NOT NULL DEFAULT 0,
                    last_test_at DATETIME NULL,
                    last_test_ok TINYINT(1) NULL,
                    last_test_message VARCHAR(500) NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX ix_payment_channels_platform (platform)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
        else:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS payment_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_code VARCHAR(32) NOT NULL UNIQUE,
                    channel_name VARCHAR(50) NOT NULL,
                    display_name VARCHAR(100) NOT NULL,
                    platform VARCHAR(20) NOT NULL,
                    provider VARCHAR(20) NOT NULL,
                    is_enabled BOOLEAN NOT NULL DEFAULT 0,
                    is_complete BOOLEAN NOT NULL DEFAULT 0,
                    config_json TEXT NULL,
                    notify_url VARCHAR(500),
                    return_url VARCHAR(500),
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    last_test_at DATETIME,
                    last_test_ok BOOLEAN,
                    last_test_message VARCHAR(500),
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))

    # 鈹€鈹€ 2) 4 鏉＄瀛愶紙鎸?channel_code 骞傜瓑鎻掑叆锛夆攢鈹€
    # [Bug 淇] 鏄惧紡鍐欏叆 created_at / updated_at锛岄伩鍏嶆煇浜?sql_mode/鏃跺尯涓?    # DEFAULT CURRENT_TIMESTAMP 涓嶇敓鏁堝鑷村瓧娈典负 NULL锛岃繘鑰岃鎺ュ彛杩斿洖鏃?    # Pydantic 鏍￠獙 created_at: datetime 澶辫触銆?    seeds = [
        ("wechat_miniprogram", "寰俊灏忕▼搴忔敮浠?, "寰俊鏀粯", "miniprogram", "wechat", 10),
        ("wechat_app", "寰俊APP鏀粯", "寰俊鏀粯", "app", "wechat", 10),
        ("alipay_h5", "鏀粯瀹滺5鏀粯", "鏀粯瀹?, "h5", "alipay", 10),
        ("alipay_app", "鏀粯瀹滱PP鏀粯", "鏀粯瀹?, "app", "alipay", 20),
    ]
    for code, name, disp, platform, provider, sort_order in seeds:
        try:
            row = (await conn.execute(
                text("SELECT id FROM payment_channels WHERE channel_code = :c"),
                {"c": code},
            )).fetchone()
            if row is None:
                await conn.execute(
                    text(
                        "INSERT INTO payment_channels "
                        "(channel_code, channel_name, display_name, platform, provider, "
                        "is_enabled, is_complete, sort_order, created_at, updated_at) "
                        "VALUES (:code, :name, :disp, :platform, :provider, 0, 0, :sort, "
                        "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {"code": code, "name": name, "disp": disp, "platform": platform,
                     "provider": provider, "sort": sort_order},
                )
        except Exception as e:
            print(f"[schema_sync] payment_channels seed insert warn: {e}")

    # 鈹€鈹€ 2.5) [Bug 淇] 鍥炶ˉ鍘嗗彶绉嶅瓙鐨?NULL 鏃堕棿鎴?鈹€鈹€
    # 鏌愪簺鐜涓嬫棭鏈熺瀛?INSERT 娌℃樉寮忓甫 created_at/updated_at锛?    # 鍙堝洜 sql_mode/鏃跺尯闂 DEFAULT CURRENT_TIMESTAMP 娌¤嚜鍔ㄥ～锛?    # 瀵艰嚧 SELECT 鍑烘潵杩欎袱涓瓧娈典负 NULL锛岃 Pydantic 鏍￠獙澶辫触銆?    try:
        await conn.execute(text(
            "UPDATE payment_channels SET created_at = CURRENT_TIMESTAMP "
            "WHERE created_at IS NULL"
        ))
        await conn.execute(text(
            "UPDATE payment_channels SET updated_at = CURRENT_TIMESTAMP "
            "WHERE updated_at IS NULL"
        ))
    except Exception as e:
        print(f"[schema_sync] payment_channels backfill timestamps warn: {e}")

    # 鈹€鈹€ 3) orders 鍔犲垪 鈹€鈹€
    if info["orders_cols"] is not None:
        cols = info["orders_cols"]
        if "payment_channel_code" not in cols:
            try:
                await conn.execute(text(
                    "ALTER TABLE orders ADD COLUMN payment_channel_code VARCHAR(32) NULL"
                ))
                try:
                    await conn.execute(text(
                        "CREATE INDEX ix_orders_payment_channel_code ON orders(payment_channel_code)"
                    ))
                except Exception:
                    pass
            except Exception as e:
                print(f"[schema_sync] orders add payment_channel_code warn: {e}")
        if "payment_display_name" not in cols:
            try:
                await conn.execute(text(
                    "ALTER TABLE orders ADD COLUMN payment_display_name VARCHAR(100) NULL"
                ))
            except Exception as e:
                print(f"[schema_sync] orders add payment_display_name warn: {e}")

    # 鈹€鈹€ 4) unified_orders 鍔犲垪 鈹€鈹€
    if info["uo_cols"] is not None:
        cols = info["uo_cols"]
        if "payment_channel_code" not in cols:
            try:
                await conn.execute(text(
                    "ALTER TABLE unified_orders ADD COLUMN payment_channel_code VARCHAR(32) NULL"
                ))
                try:
                    await conn.execute(text(
                        "CREATE INDEX ix_unified_orders_payment_channel_code ON unified_orders(payment_channel_code)"
                    ))
                except Exception:
                    pass
            except Exception as e:
                print(f"[schema_sync] unified_orders add payment_channel_code warn: {e}")
        if "payment_display_name" not in cols:
            try:
                await conn.execute(text(
                    "ALTER TABLE unified_orders ADD COLUMN payment_display_name VARCHAR(100) NULL"
                ))
            except Exception as e:
                print(f"[schema_sync] unified_orders add payment_display_name warn: {e}")

    # 鈹€鈹€ 5) [闆跺厓鍗?v2.2 + H5 浼樻儬鍒?0 鍏冧笅鍗曚慨澶?v1.0 路 B2] unified_orders.payment_method ENUM 鎵╁垪 鈹€鈹€
    # 鏃?ENUM:           ('wechat','alipay','points')
    # 闆跺厓鍗?v2.2 澧炲姞: + 'coupon_deduction'
    # 鏈锛坴1.0 路 B2锛夊啀澧炲姞: + 'balance'锛堝崰浣嶏紝涓?admin "浣欓鏀粯" 鏄剧ず鏄犲皠瀵归綈锛屼笟鍔″皻鏈疄鐜帮級
    # 蹇呴』鍦?DB 涓?MODIFY COLUMN 鍚屾鍏ㄩ儴 5 涓€硷紝鍚﹀垯鎻掑叆鎶?1265 Data truncated銆?    # 骞傜瓑锛氶€氳繃 information_schema 妫€鏌ュ垪瀹氫箟锛岀己鍝釜琛ュ摢涓€?    if info["uo_cols"] is not None and dialect_name == "mysql":
        try:
            row = (await conn.execute(text(
                "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'unified_orders' "
                "AND COLUMN_NAME = 'payment_method'"
            ))).fetchone()
            col_type = (row[0] if row and row[0] else "").lower()
            # 鍙浠绘剰涓€涓灇涓惧€肩己澶憋紝灏辨妸鍒楀畾涔夐噸鍐欎负瀹屾暣鐨?5 鍊肩増鏈紙骞傜瓑锛?            if col_type and (
                "coupon_deduction" not in col_type
                or "'balance'" not in col_type
            ):
                await conn.execute(text(
                    "ALTER TABLE unified_orders MODIFY COLUMN payment_method "
                    "ENUM('wechat','alipay','points','coupon_deduction','balance') NULL"
                ))
        except Exception as e:
            print(f"[schema_sync] unified_orders modify payment_method enum warn: {e}")


async def _sync_reschedule_columns(conn: AsyncConnection) -> None:
    """[鏍搁攢璁㈠崟杩囨湡+鏀规湡瑙勫垯浼樺寲 v1.0] 缁?products / unified_orders 澧為噺鍔犲垪銆?
    鏂板瀛楁锛?      - products.allow_reschedule          BOOLEAN/TINYINT(1) NOT NULL DEFAULT 1
      - unified_orders.reschedule_count    INT NOT NULL DEFAULT 0
      - unified_orders.reschedule_limit    INT NOT NULL DEFAULT 3

    骞傜瓑锛氭鏌?information_schema.COLUMNS 鍚庡啀 ALTER锛涗换浣曞け璐ラ兘浠?print warn 涓嶆姏閿欍€?    """
    try:
        dialect_name = conn.dialect.name
    except Exception:
        dialect_name = ""

    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        return {
            "products_cols": (
                {col["name"] for col in inspector.get_columns("products")}
                if "products" in tables else None
            ),
            "uo_cols": (
                {col["name"] for col in inspector.get_columns("unified_orders")}
                if "unified_orders" in tables else None
            ),
        }

    info = await conn.run_sync(_load)

    # 鈹€鈹€ products.allow_reschedule 鈹€鈹€
    if info["products_cols"] is not None and "allow_reschedule" not in info["products_cols"]:
        try:
            if dialect_name == "mysql":
                await conn.execute(text(
                    "ALTER TABLE products ADD COLUMN allow_reschedule TINYINT(1) "
                    "NOT NULL DEFAULT 1"
                ))
            else:
                await conn.execute(text(
                    "ALTER TABLE products ADD COLUMN allow_reschedule BOOLEAN "
                    "NOT NULL DEFAULT 1"
                ))
        except Exception as e:
            print(f"[schema_sync] products add allow_reschedule warn: {e}")

    # 鈹€鈹€ unified_orders.reschedule_count / reschedule_limit 鈹€鈹€
    if info["uo_cols"] is not None:
        cols = info["uo_cols"]
        if "reschedule_count" not in cols:
            try:
                await conn.execute(text(
                    "ALTER TABLE unified_orders ADD COLUMN reschedule_count "
                    "INT NOT NULL DEFAULT 0"
                ))
            except Exception as e:
                print(f"[schema_sync] unified_orders add reschedule_count warn: {e}")
        if "reschedule_limit" not in cols:
            try:
                await conn.execute(text(
                    "ALTER TABLE unified_orders ADD COLUMN reschedule_limit "
                    "INT NOT NULL DEFAULT 3"
                ))
            except Exception as e:
                print(f"[schema_sync] unified_orders add reschedule_limit warn: {e}")


async def _sync_medication_reminders_prd469_v2(conn: AsyncConnection) -> None:
    """[PRD-469 v2 P0] 涓?medication_reminders 琛ㄨˉ鍏呮柊瀛楁銆?""

    def _load(sync_conn):
        inspector = inspect(sync_conn)
        if "medication_reminders" not in set(inspector.get_table_names()):
            return None
        return {col["name"] for col in inspector.get_columns("medication_reminders")}

    cols = await conn.run_sync(_load)
    if cols is None:
        return
    if "frequency_per_day" not in cols:
        try:
            await conn.execute(text("ALTER TABLE medication_reminders ADD COLUMN frequency_per_day INT NULL"))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.frequency_per_day add warn: {e}")
    if "custom_times" not in cols:
        try:
            await conn.execute(text("ALTER TABLE medication_reminders ADD COLUMN custom_times JSON NULL"))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.custom_times add warn: {e}")
    if "start_date" not in cols:
        try:
            await conn.execute(text("ALTER TABLE medication_reminders ADD COLUMN start_date DATE NULL"))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.start_date add warn: {e}")
    if "end_date" not in cols:
        try:
            await conn.execute(text("ALTER TABLE medication_reminders ADD COLUMN end_date DATE NULL"))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.end_date add warn: {e}")
    if "long_term" not in cols:
        try:
            await conn.execute(text("ALTER TABLE medication_reminders ADD COLUMN long_term TINYINT(1) DEFAULT 0"))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.long_term add warn: {e}")
    if "reminder_enabled" not in cols:
        try:
            await conn.execute(text("ALTER TABLE medication_reminders ADD COLUMN reminder_enabled TINYINT(1) DEFAULT 1"))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.reminder_enabled add warn: {e}")
    if "disease_tags" not in cols:
        try:
            await conn.execute(text("ALTER TABLE medication_reminders ADD COLUMN disease_tags JSON NULL"))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.disease_tags add warn: {e}")
    # [PRD-MED-PLAN-V1 2026-05-16] 缁撴瀯鍖栧墏閲?+ 鏈嶇敤鍛ㄦ湡 + 鐢ㄨ嵂鎸囧
    if "dosage_value" not in cols:
        try:
            await conn.execute(text("ALTER TABLE medication_reminders ADD COLUMN dosage_value VARCHAR(16) NULL"))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.dosage_value add warn: {e}")
    if "dosage_unit" not in cols:
        try:
            await conn.execute(text("ALTER TABLE medication_reminders ADD COLUMN dosage_unit VARCHAR(16) NULL"))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.dosage_unit add warn: {e}")
    if "duration_days" not in cols:
        try:
            await conn.execute(text("ALTER TABLE medication_reminders ADD COLUMN duration_days INT NULL"))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.duration_days add warn: {e}")
    if "guidance" not in cols:
        try:
            await conn.execute(text("ALTER TABLE medication_reminders ADD COLUMN guidance VARCHAR(16) NULL"))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.guidance add warn: {e}")
    # [PRD-AI-DRUG-CARD-MEDPLAN-V1 2026-05-18] 鍜ㄨ浜哄綊灞?+ 閫氱敤鍚嶏紙鐢ㄤ簬瀹芥澗鍖归厤锛?    if "family_member_id" not in cols:
        try:
            await conn.execute(text(
                "ALTER TABLE medication_reminders ADD COLUMN family_member_id INT NULL, "
                "ADD INDEX ix_medication_reminders_family_member_id (family_member_id)"
            ))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.family_member_id add warn: {e}")
    if "generic_name" not in cols:
        try:
            await conn.execute(text("ALTER TABLE medication_reminders ADD COLUMN generic_name VARCHAR(200) NULL"))
        except Exception as e:
            print(f"[schema_sync] medication_reminders.generic_name add warn: {e}")


async def _sync_reminder_settings_med_v1(conn: AsyncConnection) -> None:
    """[PRD-MED-PLAN-V1 2026-05-16] 涓?reminder_settings 澧炲姞 medication_ai_call_enabled 瀛楁銆?""

    def _load(sync_conn):
        inspector = inspect(sync_conn)
        if "reminder_settings" not in set(inspector.get_table_names()):
            return None
        return {col["name"] for col in inspector.get_columns("reminder_settings")}

    cols = await conn.run_sync(_load)
    if cols is None:
        return
    if "medication_ai_call_enabled" not in cols:
        try:
            await conn.execute(text(
                "ALTER TABLE reminder_settings ADD COLUMN medication_ai_call_enabled TINYINT(1) NOT NULL DEFAULT 0"
            ))
        except Exception as e:
            print(f"[schema_sync] reminder_settings.medication_ai_call_enabled add warn: {e}")


async def _sync_family_guardian_v1(conn: AsyncConnection) -> None:
    """[PRD-FAMILY-GUARDIAN-V1] 瀹跺涵浣撴寮傚父瀹堟姢鎺ㄩ€侊細
    - family_members 鏂板 virtual_phone
    - 鏂板缓 abnormal_thresholds / alert_message_templates / family_alert_logs / virtual_member_migrations
    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        fm_cols = set()
        if "family_members" in tables:
            fm_cols = {col["name"] for col in inspector.get_columns("family_members")}
        return tables, fm_cols

    tables, fm_cols = await conn.run_sync(_load)

    if "family_members" in tables and "virtual_phone" not in fm_cols:
        try:
            await conn.execute(text(
                "ALTER TABLE family_members ADD COLUMN virtual_phone VARCHAR(20) NULL"
            ))
            await conn.execute(text(
                "CREATE INDEX idx_fm_virtual_phone ON family_members (virtual_phone)"
            ))
        except Exception as e:
            print(f"[schema_sync] family_members.virtual_phone add warn: {e}")

    if "abnormal_thresholds" not in tables:
        await conn.execute(text(
            """
            CREATE TABLE abnormal_thresholds (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                metric_code VARCHAR(64) NOT NULL,
                metric_name VARCHAR(128) NOT NULL,
                severity VARCHAR(16) NOT NULL DEFAULT 'warning',
                lower_bound DECIMAL(12,4) NULL,
                upper_bound DECIMAL(12,4) NULL,
                unit VARCHAR(32) NULL,
                gender VARCHAR(8) NULL,
                age_min INT NULL,
                age_max INT NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                INDEX idx_metric_code (metric_code)
            )
            """
        ))

    if "alert_message_templates" not in tables:
        await conn.execute(text(
            """
            CREATE TABLE alert_message_templates (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                code VARCHAR(64) NOT NULL UNIQUE,
                channel VARCHAR(16) NOT NULL,
                scene VARCHAR(32) NOT NULL,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        ))
        # 绉嶅瓙鏁版嵁锛氭瀬绠€涓夊崰浣嶆枃妗?        now = "NOW()"
        await conn.execute(text(
            f"""
            INSERT INTO alert_message_templates (code, channel, scene, title, content, is_active, created_at, updated_at) VALUES
            ('checkup_abnormal_mini', 'mini_subscribe', 'checkup_abnormal', '浣撴寮傚父鎻愰啋',
             '鎮ㄧ殑{{relationship}}{{nickname}}鐨勪綋妫€鎶ュ憡鏈?{{count}} 椤瑰紓甯革紝璇峰強鏃跺叧娉?, 1, {now}, {now}),
            ('checkup_abnormal_wechat', 'wechat_mp', 'checkup_abnormal', '浣撴寮傚父鎻愰啋',
             '鎮ㄧ殑{{relationship}}{{nickname}}鐨勪綋妫€鎶ュ憡鏈?{{count}} 椤瑰紓甯革紝鐐瑰嚮鏌ョ湅璇︽儏', 1, {now}, {now}),
            ('checkup_abnormal_app', 'app_push', 'checkup_abnormal', '浣撴寮傚父鎻愰啋',
             '鎮ㄧ殑{{relationship}}{{nickname}}鐨勪綋妫€鎶ュ憡鏈?{{count}} 椤瑰紓甯革紝璇峰強鏃跺叧娉?, 1, {now}, {now}),
            ('family_bind_success', 'mini_subscribe', 'family_bind', '瀹堟姢鍏崇郴寤虹珛鎴愬姛',
             '{{nickname}} 宸叉垚涓烘偍鐨勫畧鎶よ€咃紝鍙湪绗竴鏃堕棿鏀跺埌鎮ㄧ殑鍋ュ悍鎻愰啋', 1, {now}, {now}),
            ('family_unbind_notify', 'mini_subscribe', 'family_unbind', '瀹堟姢鍏崇郴瑙ｉ櫎鎻愰啋',
             '{{nickname}} 宸茶В闄や笌鎮ㄧ殑瀹堟姢鍏崇郴', 1, {now}, {now})
            """
        ))

    if "family_alert_logs" not in tables:
        await conn.execute(text(
            """
            CREATE TABLE family_alert_logs (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                member_id INT NOT NULL,
                guardian_user_id INT NOT NULL,
                report_id INT NULL,
                severity VARCHAR(16) NOT NULL DEFAULT 'warning',
                abnormal_count INT NOT NULL DEFAULT 0,
                template_code VARCHAR(64) NOT NULL DEFAULT 'checkup_abnormal',
                channel VARCHAR(16) NOT NULL DEFAULT 'mini_subscribe',
                delivery_status VARCHAR(16) NOT NULL DEFAULT 'sent',
                error_msg VARCHAR(255) NULL,
                pushed_at DATETIME NOT NULL,
                clicked_at DATETIME NULL,
                is_archived TINYINT(1) NOT NULL DEFAULT 0,
                INDEX idx_member_pushed (member_id, pushed_at),
                INDEX idx_guardian_pushed (guardian_user_id, pushed_at),
                INDEX idx_status (delivery_status)
            )
            """
        ))

    if "virtual_member_migrations" not in tables:
        await conn.execute(text(
            """
            CREATE TABLE virtual_member_migrations (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                member_id INT NOT NULL,
                target_user_id INT NOT NULL,
                creator_user_id INT NOT NULL,
                virtual_phone VARCHAR(20) NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                created_at DATETIME NOT NULL,
                confirmed_at DATETIME NULL,
                INDEX idx_target (target_user_id, status),
                INDEX idx_member (member_id)
            )
            """
        ))


async def _sync_family_members_archive_optim_v2(conn: AsyncConnection) -> None:
    """[PRD-HEALTH-ARCHIVE-OPTIM-V2 2026-05-18] family_members 鏂板 4 鍒楋細
    - avatar_color_index TINYINT NULL锛?-4 寰幆锛?    - ai_call_enabled BOOLEAN DEFAULT FALSE
    - ai_call_timing VARCHAR(16) DEFAULT 'on_time'
    - guardian_alert_minutes TINYINT DEFAULT 5
    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "family_members" not in tables:
            return set()
        return {col["name"] for col in inspector.get_columns("family_members")}

    cols = await conn.run_sync(_load)
    if not cols:
        return

    if "avatar_color_index" not in cols:
        try:
            await conn.execute(text(
                "ALTER TABLE family_members ADD COLUMN avatar_color_index TINYINT NULL"
            ))
        except Exception as e:
            print(f"[schema_sync] family_members.avatar_color_index add warn: {e}")
    if "ai_call_enabled" not in cols:
        try:
            await conn.execute(text(
                "ALTER TABLE family_members ADD COLUMN ai_call_enabled TINYINT(1) NOT NULL DEFAULT 0"
            ))
        except Exception as e:
            print(f"[schema_sync] family_members.ai_call_enabled add warn: {e}")
    if "ai_call_timing" not in cols:
        try:
            await conn.execute(text(
                "ALTER TABLE family_members ADD COLUMN ai_call_timing VARCHAR(16) NOT NULL DEFAULT 'on_time'"
            ))
        except Exception as e:
            print(f"[schema_sync] family_members.ai_call_timing add warn: {e}")
    if "guardian_alert_minutes" not in cols:
        try:
            await conn.execute(text(
                "ALTER TABLE family_members ADD COLUMN guardian_alert_minutes TINYINT NOT NULL DEFAULT 5"
            ))
        except Exception as e:
            print(f"[schema_sync] family_members.guardian_alert_minutes add warn: {e}")

    # [PRD-FAMILY-V3-STATUS-INPLACE-UPGRADE 2026-06-03] V3 涓?瀛愮姸鎬佸師鍦板崌绾?    # 1) 鏂板 sub_status 鍒?+ 3 涓緟鍔╁璁″垪(涓嶅姩 status 鍒楀悕)
    # 2) 鏁版嵁杩佺Щ:active鈫抌ound, removed鈫抎eleted(self_deleted), deleted鈫抎eleted(admin_deleted)
    # 3) 鍥炴壂 family_management 涓?cancelled 鐨勫叧绯?鎶婃垚鍛樺崱鐗囨爣璁颁负 unbound/unbinded
    if "sub_status" not in cols:
        try:
            await conn.execute(text(
                "ALTER TABLE family_members ADD COLUMN sub_status VARCHAR(30) NULL"
            ))
        except Exception as e:
            print(f"[schema_sync] family_members.sub_status add warn: {e}")
    if "status_changed_at" not in cols:
        try:
            await conn.execute(text(
                "ALTER TABLE family_members ADD COLUMN status_changed_at DATETIME NULL"
            ))
        except Exception as e:
            print(f"[schema_sync] family_members.status_changed_at add warn: {e}")
    if "status_changed_by" not in cols:
        try:
            await conn.execute(text(
                "ALTER TABLE family_members ADD COLUMN status_changed_by INT NULL"
            ))
        except Exception as e:
            print(f"[schema_sync] family_members.status_changed_by add warn: {e}")
    if "status_reason" not in cols:
        try:
            await conn.execute(text(
                "ALTER TABLE family_members ADD COLUMN status_reason VARCHAR(100) NULL"
            ))
        except Exception as e:
            print(f"[schema_sync] family_members.status_reason add warn: {e}")

    # 鏁版嵁杩佺Щ:浠呭綋瀛樺湪 active/removed 鑰佹灇涓炬椂鎵嶆墽琛?涓斿彧璺戜竴娆?骞傜瓑)
    try:
        # 2.1 active 鈫?bound/bound
        await conn.execute(text(
            "UPDATE family_members SET status='bound', sub_status='bound', "
            "status_changed_at=NOW(), status_reason='V3_MIGRATION' "
            "WHERE status='active'"
        ))
        # 2.2 removed 鈫?deleted/self_deleted
        await conn.execute(text(
            "UPDATE family_members SET status='deleted', sub_status='self_deleted', "
            "status_changed_at=NOW(), status_reason='V3_MIGRATION' "
            "WHERE status='removed'"
        ))
        # 2.3 deleted 浣?sub_status 涓虹┖ 鈫?琛?admin_deleted
        await conn.execute(text(
            "UPDATE family_members SET sub_status='admin_deleted', "
            "status_changed_at=COALESCE(status_changed_at, NOW()), "
            "status_reason=COALESCE(status_reason, 'V3_MIGRATION') "
            "WHERE status='deleted' AND (sub_status IS NULL OR sub_status='')"
        ))
        # 2.4 鍥炴壂 family_management cancelled 鈫?鎴愬憳鏍囪涓?unbound/unbinded
        await conn.execute(text(
            "UPDATE family_members fm "
            "JOIN family_management mg "
            "  ON mg.managed_member_id = fm.id AND mg.manager_user_id = fm.user_id "
            "SET fm.status='unbound', fm.sub_status='unbinded', "
            "    fm.status_changed_at=COALESCE(mg.updated_at, NOW()), "
            "    fm.status_reason='V3_MIGRATION_UNBIND' "
            "WHERE mg.status IN ('cancelled', 'removed', 'cancelled_by_target') "
            "  AND fm.status='bound'"
        ))
        # 2.5 鍏滃簳:浠讳綍 sub_status 浠嶄负绌虹殑 bound 璁板綍琛?bound
        await conn.execute(text(
            "UPDATE family_members SET sub_status='bound' "
            "WHERE status='bound' AND (sub_status IS NULL OR sub_status='')"
        ))
    except Exception as e:
        print(f"[schema_sync] family_members V3 status migration warn: {e}")

    # 宸插瓨鍦ㄦ暟鎹ˉ鍏?avatar_color_index锛氭寜 user_id 鍐呯殑 created_at 椤哄簭寰幆
    try:
        await conn.execute(text(
            """
            UPDATE family_members fm
            JOIN (
                SELECT id,
                       (ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at, id) - 1) %% 5 AS idx
                FROM family_members
                WHERE avatar_color_index IS NULL
            ) t ON fm.id = t.id
            SET fm.avatar_color_index = t.idx
            WHERE fm.avatar_color_index IS NULL
            """
        ))
    except Exception as e:
        print(f"[schema_sync] family_members.avatar_color_index backfill warn: {e}")


async def _sync_chat_session_idle_archive_v1(conn: AsyncConnection) -> None:
    """[PRD-AI-HOME-IDLE-ARCHIVE-V1 2026-05-19] chat_sessions 澧炲姞 status/archived_at/last_active_at

    骞傜瓑锛氭娴嬪垪鏄惁瀛樺湪锛涘缓绔嬮儴鍒嗘€х害鏉燂紙MySQL 涓嶆敮鎸?partial index 鈫?搴旂敤灞備繚璇佸敮涓€锛夈€?    杩佺Щ瑙勫垯锛堟寜 PRD 绗?4 鑺傦級锛?      1) ADD COLUMN status / archived_at / last_active_at
      2) 鍥炲～ last_active_at = updated_at
      3) message_count = 0 鐨勭┖浼氳瘽杞垹闄わ紙is_deleted = TRUE锛?      4) 鍏朵綑瀛橀噺浼氳瘽缃负 archived锛屽洖濉?archived_at = updated_at
      5) 寤虹珛 (user_id, status, last_active_at) 澶嶅悎绱㈠紩浠ュ姞閫熷垪琛ㄦ煡璇?    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "chat_sessions" not in tables:
            return None, set()
        cols = {col["name"] for col in inspector.get_columns("chat_sessions")}
        idx_names = {idx.get("name") for idx in inspector.get_indexes("chat_sessions") if idx.get("name")}
        return cols, idx_names

    session_cols, idx_names = await conn.run_sync(_load)
    if session_cols is None:
        return

    altered = False
    if "status" not in session_cols:
        try:
            await conn.execute(text(
                "ALTER TABLE chat_sessions ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'archived'"
            ))
            altered = True
        except Exception as e:
            print(f"[schema_sync] chat_sessions add status warn: {e}")
    if "archived_at" not in session_cols:
        try:
            await conn.execute(text(
                "ALTER TABLE chat_sessions ADD COLUMN archived_at DATETIME NULL"
            ))
            altered = True
        except Exception as e:
            print(f"[schema_sync] chat_sessions add archived_at warn: {e}")
    if "last_active_at" not in session_cols:
        try:
            await conn.execute(text(
                "ALTER TABLE chat_sessions ADD COLUMN last_active_at DATETIME NULL"
            ))
            altered = True
        except Exception as e:
            print(f"[schema_sync] chat_sessions add last_active_at warn: {e}")

    # 鏁版嵁杩佺Щ锛堝箓绛夛級锛氬彧鏈夌涓€娆￠渶瑕佸洖濉紝浣嗘瘡娆″惎鍔ㄤ篃瀹夊叏锛堝熀浜?is_deleted/鐘舵€佺瓑鏉′欢杩囨护锛?    if altered or "status" not in session_cols or "last_active_at" not in session_cols:
        try:
            await conn.execute(text(
                "UPDATE chat_sessions SET last_active_at = COALESCE(updated_at, created_at, NOW()) "
                "WHERE last_active_at IS NULL"
            ))
        except Exception as e:
            print(f"[schema_sync] chat_sessions backfill last_active_at warn: {e}")
        try:
            # 绌轰細璇濓紙鏃犱换浣曟秷鎭級涓€娆℃€ц蒋鍒犻櫎锛堣剰鏁版嵁娓呯悊锛?            await conn.execute(text(
                "UPDATE chat_sessions SET is_deleted = 1 "
                "WHERE (message_count IS NULL OR message_count = 0) AND (is_deleted IS NULL OR is_deleted = 0)"
            ))
        except Exception as e:
            print(f"[schema_sync] chat_sessions soft-delete empty warn: {e}")
        try:
            # 鍏朵綑瀛橀噺浼氳瘽缃负 archived锛坅rchived_at 鍥炲～锛?            await conn.execute(text(
                "UPDATE chat_sessions SET status = 'archived', "
                "archived_at = COALESCE(archived_at, updated_at, created_at, NOW()) "
                "WHERE status IS NULL OR status = '' OR (status = 'archived' AND archived_at IS NULL)"
            ))
        except Exception as e:
            print(f"[schema_sync] chat_sessions backfill archived warn: {e}")

    # 寤虹储寮曪紙骞傜瓑锛?    if "idx_status_last_active" not in idx_names:
        try:
            await conn.execute(text(
                "CREATE INDEX idx_status_last_active ON chat_sessions (user_id, status, last_active_at)"
            ))
        except Exception as e:
            print(f"[schema_sync] chat_sessions add idx_status_last_active warn: {e}")


async def _sync_guardian_ai_call_settings_v1(conn: AsyncConnection) -> None:
    """[PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] 鍒涘缓 guardian_ai_call_settings 琛ㄣ€?
    姣忎釜 (owner_user_id, target_user_id) 鍞竴涓€浠介厤缃紝琚畧鎶や汉鍚嶄笅鎵€鏈夌敤鑽鍒掑叡鐢ㄣ€?    """
    def _has_table(sync_conn) -> bool:
        return "guardian_ai_call_settings" in set(inspect(sync_conn).get_table_names())

    exists = await conn.run_sync(_has_table)
    if exists:
        return
    await conn.execute(text(
        """
        CREATE TABLE guardian_ai_call_settings (
            id INT NOT NULL AUTO_INCREMENT,
            owner_user_id INT NOT NULL,
            target_user_id INT NOT NULL,
            enabled TINYINT(1) NOT NULL DEFAULT 0,
            dnd_start VARCHAR(8) NULL DEFAULT '22:00',
            dnd_end VARCHAR(8) NULL DEFAULT '07:00',
            call_target VARCHAR(16) NOT NULL DEFAULT 'self',
            created_at DATETIME NULL,
            updated_at DATETIME NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uk_guardian_aicall_owner_target (owner_user_id, target_user_id),
            INDEX ix_gacs_owner (owner_user_id),
            INDEX ix_gacs_target (target_user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    ))


async def _sync_membership_v1(conn: AsyncConnection) -> None:
    """[浠樿垂浼氬憳浣撶郴 PRD v1.1] 鍒涘缓 membership_plans / user_memberships / free_member_quota 琛紝
    骞剁粰 products 琛ㄦ坊鍔?is_member_discount_eligible 瀛楁锛堝箓绛夛級銆?    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        product_cols = (
            {col["name"] for col in inspector.get_columns("products")}
            if "products" in tables else set()
        )
        return tables, product_cols

    tables, product_cols = await conn.run_sync(_load)

    if "membership_plans" not in tables:
        # [PRD v1.0 缁堢瀵归綈 2026-05-26] 鏂板缓琛ㄦ椂鐩存帴浣跨敤鏈€缁堝瓧娈甸泦
        await conn.execute(text(
            """
            CREATE TABLE membership_plans (
                id INT NOT NULL AUTO_INCREMENT,
                name VARCHAR(50) NOT NULL,
                description VARCHAR(255) NULL,
                price_month DECIMAL(10,2) NULL,
                price_year DECIMAL(10,2) NULL,
                max_managed INT NOT NULL DEFAULT 3,
                ai_outbound_call_count INT NOT NULL DEFAULT 0,
                emergency_ai_call_count INT NOT NULL DEFAULT 0,
                max_managed_by INT NOT NULL DEFAULT 3,
                discount_rate FLOAT NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                is_recommended TINYINT(1) NOT NULL DEFAULT 0,
                sort_order INT NOT NULL DEFAULT 0,
                created_at DATETIME NULL,
                updated_at DATETIME NULL,
                PRIMARY KEY (id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        ))

    if "user_membership_subs" not in tables:
        await conn.execute(text(
            """
            CREATE TABLE user_membership_subs (
                id INT NOT NULL AUTO_INCREMENT,
                user_id INT NOT NULL,
                plan_id INT NOT NULL,
                billing_cycle VARCHAR(20) NOT NULL DEFAULT 'monthly',
                start_at DATETIME NOT NULL,
                expire_at DATETIME NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                paid_amount DECIMAL(10,2) NULL,
                auto_renew TINYINT(1) NOT NULL DEFAULT 0,
                created_at DATETIME NULL,
                updated_at DATETIME NULL,
                PRIMARY KEY (id),
                INDEX ix_user_membership_subs_user (user_id),
                INDEX ix_user_membership_subs_plan (plan_id),
                INDEX ix_user_membership_subs_status_expire (user_id, status, expire_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        ))

    if "free_member_quota" not in tables:
        # [PRD v1.0 缁堢瀵归綈] 鏂拌〃鐩存帴浣跨敤鏈€缁堝瓧娈甸泦
        await conn.execute(text(
            """
            CREATE TABLE free_member_quota (
                id INT NOT NULL,
                max_managed INT NOT NULL DEFAULT 3,
                ai_outbound_call_count INT NOT NULL DEFAULT 5,
                emergency_ai_call_count INT NOT NULL DEFAULT 3,
                max_managed_by INT NOT NULL DEFAULT 3,
                updated_at DATETIME NULL,
                PRIMARY KEY (id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        ))
        await conn.execute(text(
            "INSERT INTO free_member_quota (id, max_managed, ai_outbound_call_count, emergency_ai_call_count, max_managed_by, updated_at) "
            "VALUES (1, 3, 5, 3, 3, NOW()) "
            "ON DUPLICATE KEY UPDATE id=id"
        ))

    if "products" in tables and "is_member_discount_eligible" not in product_cols:
        await conn.execute(text(
            "ALTER TABLE products ADD COLUMN is_member_discount_eligible TINYINT(1) NOT NULL DEFAULT 0 "
            "COMMENT '鏄惁鏀寔浠樿垂浼氬憳鎶樻墸 (PRD v1.1)'"
        ))


async def _sync_membership_v11_max_managed_include_self_migration(conn: AsyncConnection) -> None:
    """[PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 涓€娆℃€ф暟鎹縼绉伙細
    membership_plans.max_managed 涓?free_member_quota.max_managed 鐢便€屼笉鍚湰浜恒€嶆敼涓恒€?*鍚湰浜?*銆嶈涔夈€?    鐢?schema_migration_log 琛?+ 鏍囪 key 淇濊瘉骞傜瓑銆?    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        return set(inspector.get_table_names())

    tables = await conn.run_sync(_load)

    # 1) 纭繚杩佺Щ鏃ュ織琛ㄥ瓨鍦?    if "schema_migration_log" not in tables:
        await conn.execute(text(
            """
            CREATE TABLE schema_migration_log (
                id INT NOT NULL AUTO_INCREMENT,
                migration_key VARCHAR(128) NOT NULL,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                detail VARCHAR(500) NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uk_migration_key (migration_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        ))

    MIG_KEY = "membership_v11_max_managed_include_self_20260530"

    # 2) 妫€鏌ユ槸鍚﹀凡鎵ц
    r = await conn.execute(
        text("SELECT COUNT(1) FROM schema_migration_log WHERE migration_key = :k"),
        {"k": MIG_KEY},
    )
    already = int((r.scalar() or 0))
    if already > 0:
        return

    # 3) 鎵ц +1 杩佺Щ锛?1 涓嶉檺妗ｄ繚鎸佷笉鍙橈紝>=9999 瑙嗕负宸插惈鏈汉涓嶅啀 +1锛?    if "membership_plans" in tables:
        await conn.execute(text(
            "UPDATE membership_plans SET max_managed = max_managed + 1 "
            "WHERE max_managed IS NOT NULL AND max_managed >= 0 AND max_managed < 9999"
        ))
    if "free_member_quota" in tables:
        await conn.execute(text(
            "UPDATE free_member_quota SET max_managed = max_managed + 1 "
            "WHERE max_managed IS NOT NULL AND max_managed >= 0 AND max_managed < 9999"
        ))

    # 4) 鍐欏叆杩佺Щ鏃ュ織锛屽箓绛?    await conn.execute(
        text(
            "INSERT INTO schema_migration_log (migration_key, detail) "
            "VALUES (:k, :d)"
        ),
        {
            "k": MIG_KEY,
            "d": "max_managed 鐢变笉鍚湰浜烘敼涓哄惈鏈汉璇箟锛?1 涓€娆℃€ц縼绉伙級",
        },
    )


async def _sync_guardian_system_v1(conn: AsyncConnection) -> None:
    """[瀹堟姢浜轰綋绯?PRD v1.1 2026-05-25] 鍦?family_management 琛ㄥ姞瀛楁锛屾柊寤鸿浆绉讳笌棰濆害琛紙骞傜瓑锛夈€?""
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        fm_cols = (
            {col["name"] for col in inspector.get_columns("family_management")}
            if "family_management" in tables else set()
        )
        return tables, fm_cols

    tables, fm_cols = await conn.run_sync(_load)

    if "family_management" in tables:
        if "is_primary_guardian" not in fm_cols:
            await conn.execute(text(
                "ALTER TABLE family_management ADD COLUMN is_primary_guardian TINYINT(1) "
                "NOT NULL DEFAULT 0 COMMENT '鏄惁涓诲畧鎶や汉(姣忚瀹堟姢浜哄敮涓€) PRD-GUARDIAN-V1'"
            ))
        if "priority_order" not in fm_cols:
            await conn.execute(text(
                "ALTER TABLE family_management ADD COLUMN priority_order INT NOT NULL DEFAULT 100 "
                "COMMENT '涓茶澶栧懠浼樺厛绾?涓?0,鍏朵粬瓒婂皬瓒婁紭鍏? PRD-GUARDIAN-V1'"
            ))
        # [瀹堟姢浜轰綋绯?IGUARD-V2 2026-05-28] 浼氬憳鏉冪泭鍏变韩寮€鍏筹細榛樿寮€鍚紝涓诲畧鎶や汉鍙叧闂?        if "member_benefit_shared" not in fm_cols:
            await conn.execute(text(
                "ALTER TABLE family_management ADD COLUMN member_benefit_shared TINYINT(1) "
                "NOT NULL DEFAULT 1 COMMENT '鏄惁鍚戣瀹堟姢浜哄叡浜細鍛樻潈鐩?IGUARD-V2'"
            ))
        # 鍒濆鍖栧巻鍙叉暟鎹細瀵逛簬姣忎釜琚畧鎶や汉锛屽叾鏈€鏃╃粦瀹氱殑瀹堟姢浜鸿涓轰富瀹堟姢浜?        await conn.execute(text(
            """
            UPDATE family_management fm
            JOIN (
                SELECT managed_user_id, MIN(created_at) AS first_at
                FROM family_management
                WHERE status='active'
                GROUP BY managed_user_id
            ) t ON t.managed_user_id = fm.managed_user_id AND t.first_at = fm.created_at
            SET fm.is_primary_guardian = 1, fm.priority_order = 0
            WHERE fm.status='active'
              AND NOT EXISTS (
                  SELECT 1 FROM (SELECT 1) tmp
                  WHERE fm.is_primary_guardian = 1
              )
            """
        ))

    if "guardian_transfer_requests" not in tables:
        await conn.execute(text(
            """
            CREATE TABLE guardian_transfer_requests (
                id INT NOT NULL AUTO_INCREMENT,
                managed_user_id INT NOT NULL,
                from_management_id INT NOT NULL,
                to_management_id INT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                created_at DATETIME NULL,
                expires_at DATETIME NULL,
                approved_at DATETIME NULL,
                cancelled_at DATETIME NULL,
                PRIMARY KEY (id),
                KEY idx_gtr_managed (managed_user_id),
                KEY idx_gtr_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            COMMENT '涓诲畧鎶や汉杞Щ璇锋眰 PRD-GUARDIAN-V1'
            """
        ))

    if "guardian_alert_quota_usage" not in tables:
        await conn.execute(text(
            """
            CREATE TABLE guardian_alert_quota_usage (
                id INT NOT NULL AUTO_INCREMENT,
                user_id INT NOT NULL COMMENT '娑堣€楅搴︾殑瀹堟姢浜?user_id',
                managed_user_id INT NOT NULL COMMENT '瑙﹀彂鍛婅鐨勮瀹堟姢浜?user_id',
                used_at DATETIME NULL,
                call_type VARCHAR(20) NOT NULL DEFAULT 'alert',
                PRIMARY KEY (id),
                KEY idx_gaqu_user_used (user_id, used_at),
                KEY idx_gaqu_managed (managed_user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            COMMENT '寮傚父鍛婅鍏嶈垂鐢佃瘽棰濆害浣跨敤璁板綍 PRD-GUARDIAN-V1'
            """
        ))


async def _sync_guardian_system_v12(conn: AsyncConnection) -> None:
    """[瀹堟姢浜轰綋绯?PRD v1.2 2026-05-25] v1.2 schema 鍗囩骇锛?    - membership_plans 鏂板 emergency_ai_call_count / max_managed / point_multiplier 瀛楁
    - free_member_quota 鏂板 emergency_ai_call_count / max_managed 瀛楁
    - 鏂板 guardian_proxy_pay 琛紙浠ｄ粯寮€鍏筹級
    - 鏂板 emergency_call_sources 琛紙绱ф€ュ懠鍙Е鍙戞簮绠＄悊锛? 鏉＄瀛愭暟鎹級
    - 鏂板 ai_call_reminders 琛紙AI 澶栧懠鎻愰啋鍒楄〃锛?    骞傜瓑鎵ц銆?""

    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        mp_cols = (
            {col["name"] for col in inspector.get_columns("membership_plans")}
            if "membership_plans" in tables else set()
        )
        fmq_cols = (
            {col["name"] for col in inspector.get_columns("free_member_quota")}
            if "free_member_quota" in tables else set()
        )
        return tables, mp_cols, fmq_cols

    tables, mp_cols, fmq_cols = await conn.run_sync(_load)

    # membership_plans 鏂板瀛楁
    if "membership_plans" in tables:
        if "emergency_ai_call_count" not in mp_cols:
            await conn.execute(text(
                "ALTER TABLE membership_plans ADD COLUMN emergency_ai_call_count INT NOT NULL DEFAULT 0 "
                "COMMENT '[PRD-GUARDIAN-V1.2] 绱ф€?AI 鍛煎彨棰濆害锛堟/鏈堬級锛?1=涓嶉檺'"
            ))
            # 浠庢棫鐨?ai_alert_quota 瀛楁杩佺Щ鏁版嵁
            await conn.execute(text(
                "UPDATE membership_plans SET emergency_ai_call_count = ai_alert_quota "
                "WHERE emergency_ai_call_count = 0 AND ai_alert_quota > 0"
            ))
        if "max_managed" not in mp_cols:
            await conn.execute(text(
                "ALTER TABLE membership_plans ADD COLUMN max_managed INT NOT NULL DEFAULT 10 "
                "COMMENT '[PRD-GUARDIAN-V1.2] 瀹堟姢浠栦汉涓婇檺锛堝墠绔睍绀猴級锛?1=涓嶉檺'"
            ))
        if "point_multiplier" not in mp_cols:
            await conn.execute(text(
                "ALTER TABLE membership_plans ADD COLUMN point_multiplier FLOAT NOT NULL DEFAULT 1.0 "
                "COMMENT '[PRD-GUARDIAN-V1.2] 绉垎缈诲€嶅€嶆暟'"
            ))

    # free_member_quota 鏂板瀛楁
    if "free_member_quota" in tables:
        if "emergency_ai_call_count" not in fmq_cols:
            await conn.execute(text(
                "ALTER TABLE free_member_quota ADD COLUMN emergency_ai_call_count INT NOT NULL DEFAULT 3 "
                "COMMENT '[PRD-GUARDIAN-V1.2] 鍏嶈垂绱ф€?AI 鍛煎彨棰濆害'"
            ))
            await conn.execute(text(
                "UPDATE free_member_quota SET emergency_ai_call_count = ai_alert_quota "
                "WHERE emergency_ai_call_count = 3 AND ai_alert_quota > 0"
            ))
        if "max_managed" not in fmq_cols:
            await conn.execute(text(
                "ALTER TABLE free_member_quota ADD COLUMN max_managed INT NOT NULL DEFAULT 3 "
                "COMMENT '[PRD-GUARDIAN-V1.2] 鍏嶈垂鐢ㄦ埛瀹堟姢浠栦汉涓婇檺'"
            ))

    # guardian_proxy_pay 琛?    if "guardian_proxy_pay" not in tables:
        await conn.execute(text(
            """
            CREATE TABLE guardian_proxy_pay (
                id INT NOT NULL AUTO_INCREMENT,
                primary_guardian_user_id INT NOT NULL COMMENT '涓诲畧鎶や汉 user_id',
                managed_user_id INT NOT NULL COMMENT '琚畧鎶や汉 user_id',
                enabled TINYINT(1) NOT NULL DEFAULT 0,
                created_at DATETIME NULL,
                updated_at DATETIME NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uniq_gpp_pair (primary_guardian_user_id, managed_user_id),
                KEY idx_gpp_managed (managed_user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            COMMENT '涓诲畧鎶や汉浠ｄ粯琚畧鎶や汉 AI 澶栧懠棰濆害寮€鍏?PRD-GUARDIAN-V1.2'
            """
        ))

    # emergency_call_sources 琛?    if "emergency_call_sources" not in tables:
        await conn.execute(text(
            """
            CREATE TABLE emergency_call_sources (
                id INT NOT NULL AUTO_INCREMENT,
                source_code VARCHAR(50) NOT NULL,
                source_name VARCHAR(100) NOT NULL,
                description TEXT NULL,
                is_enabled TINYINT(1) NOT NULL DEFAULT 1,
                is_builtin TINYINT(1) NOT NULL DEFAULT 0,
                trigger_condition TEXT NULL,
                applicable_device_type VARCHAR(100) NULL,
                sort_order INT NOT NULL DEFAULT 0,
                created_at DATETIME NULL,
                updated_at DATETIME NULL,
                PRIMARY KEY (id),
                UNIQUE KEY uniq_source_code (source_code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            COMMENT '绱ф€ュ懠鍙Е鍙戞簮绠＄悊 PRD-GUARDIAN-V1.2'
            """
        ))

    # [绱ф€ュ懠鍙Е鍙戞簮绠＄悊 v1.0 2026-05-25] 4 鏉″唴缃瀛愬箓绛?upsert
    # 娉ㄦ剰锛氭湰鍧楀湪姣忔鍚姩鏃堕兘浼氭墽琛岋紝鑷姩淇鍘嗗彶涓枃涔辩爜璁板綍銆?    # 鏂囨涓恒€岀揣鎬ュ懠鍙Е鍙戞簮绠＄悊 v1.0銆嶆渶缁堝弬鑰冪増銆?    await conn.execute(text(
        """
        INSERT INTO emergency_call_sources
          (source_code, source_name, description, is_enabled, is_builtin, sort_order, created_at, updated_at)
        VALUES
          ('health_data_abnormal',
           '鍋ュ悍鏁版嵁寮傚父',
           '褰撶敤鎴风殑鍋ュ悍鏁版嵁锛堝蹇冪巼銆佽鍘嬨€佽姘э級瓒呭嚭瀹夊叏闃堝€兼椂鑷姩瑙﹀彂',
           1, 1, 1, NOW(), NOW()),
          ('smoke_alarm',
           '鐑熼浘鎶ヨ',
           '褰撳涓儫闆句紶鎰熷櫒妫€娴嬪埌鐑熼浘娴撳害寮傚父鏃惰Е鍙戠揣鎬ュ懠鍙?,
           1, 1, 2, NOW(), NOW()),
          ('water_alarm',
           '娴告按鎶ヨ',
           '褰撳涓蹈姘翠紶鎰熷櫒妫€娴嬪埌婕忔按鎴栫Н姘存椂瑙﹀彂绱ф€ュ懠鍙?,
           1, 1, 3, NOW(), NOW()),
          ('emergency_button',
           '绱ф€ユ寜閽?,
           '褰撶敤鎴锋寜涓嬮殢韬垨瀹朵腑鐨勪竴閿揣鎬ュ懠鍙寜閽椂绔嬪嵆瑙﹀彂',
           1, 1, 4, NOW(), NOW())
        ON DUPLICATE KEY UPDATE
          source_name = VALUES(source_name),
          description = VALUES(description),
          is_enabled  = 1,
          is_builtin  = 1,
          updated_at  = NOW()
        """
    ))

    # ai_call_reminders 琛?    if "ai_call_reminders" not in tables:
        await conn.execute(text(
            """
            CREATE TABLE ai_call_reminders (
                id INT NOT NULL AUTO_INCREMENT,
                setter_user_id INT NOT NULL,
                target_user_id INT NOT NULL,
                reminder_type VARCHAR(40) NOT NULL DEFAULT 'general',
                title VARCHAR(100) NOT NULL,
                content TEXT NULL,
                schedule_cron VARCHAR(100) NULL,
                next_fire_at DATETIME NULL,
                is_enabled TINYINT(1) NOT NULL DEFAULT 1,
                is_paused_by_quota TINYINT(1) NOT NULL DEFAULT 0,
                created_at DATETIME NULL,
                updated_at DATETIME NULL,
                PRIMARY KEY (id),
                KEY idx_acr_setter (setter_user_id),
                KEY idx_acr_target (target_user_id),
                KEY idx_acr_next_fire (next_fire_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            COMMENT 'AI 澶栧懠鎻愰啋 PRD-GUARDIAN-V1.2'
            """
        ))


async def _sync_drop_default_health_tasks_v1(conn: AsyncConnection) -> None:
    """[鍋ュ悍璁″垝绠＄悊鑿滃崟涓嬬嚎涓庢墦鍗＄粺璁℃惉瀹?PRD v1.0 2026-05-25]

    DROP TABLE `default_health_tasks`锛氱鐞嗗悗鍙般€屽仴搴疯鍒掔鐞?鈫?閫氱敤浠诲姟閰嶇疆銆?    鍙婂叾瀵瑰簲鏁版嵁琛ㄥ凡涓嬬嚎銆傝琛ㄤ负瀛ゅ矝鍔熻兘锛屾湭琚?H5 / 灏忕▼搴?/ Flutter App 寮曠敤锛?    鐩存帴鐗╃悊鍒犻櫎锛屼笉鍋氬浠姐€?
    骞傜瓑锛氶€氳繃 `DROP TABLE IF EXISTS` 瀹炵幇锛屽娆℃墽琛屼笉鎶ラ敊銆?    """
    def _has_table(sync_conn):
        inspector = inspect(sync_conn)
        return "default_health_tasks" in set(inspector.get_table_names())

    if not await conn.run_sync(_has_table):
        return

    await conn.execute(text("DROP TABLE IF EXISTS default_health_tasks"))


async def _sync_member_center_v2(conn: AsyncConnection) -> None:
    """[浼氬憳涓績浼樺寲 PRD v2.0 2026-05-26] order_items 鏂板 membership_plan_id / membership_period 鍒椼€?
    澶嶇敤 fulfillment_type='virtual' 鏍囪瘑鏉冪泭鏈嶅姟璁㈠崟锛涙湰涓ゅ垪闈炵┖鏃惰〃绀鸿 OrderItem 鏄細鍛樿垂璁㈠崟銆?    骞傜瓑锛氭瘡娆″惎鍔ㄦ椂妫€鏌ュ垪鏄惁瀛樺湪锛屼笉瀛樺湪鎵?ALTER銆?    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "order_items" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("order_items")}

    cols = await conn.run_sync(_load)
    if cols is None:
        return
    if "membership_plan_id" not in cols:
        await conn.execute(text(
            "ALTER TABLE order_items ADD COLUMN membership_plan_id INT NULL, "
            "ADD INDEX idx_order_items_membership_plan_id (membership_plan_id)"
        ))
    if "membership_period" not in cols:
        await conn.execute(text(
            "ALTER TABLE order_items ADD COLUMN membership_period VARCHAR(10) NULL"
        ))
    # 灏?product_id 鏀逛负鍙┖锛屼互鏀寔浼氬憳璐硅鍗曪紙鏃犲叧鑱斿疄鐗╁晢鍝侊級
    def _check_prod_nullable(sync_conn):
        inspector = inspect(sync_conn)
        for col in inspector.get_columns("order_items"):
            if col["name"] == "product_id":
                return col.get("nullable", False)
        return True

    try:
        is_nullable = await conn.run_sync(_check_prod_nullable)
        if not is_nullable:
            await conn.execute(text(
                "ALTER TABLE order_items MODIFY COLUMN product_id INT NULL"
            ))
    except Exception:
        # 涓€浜?DB锛堝 SQLite锛変笉鏀寔 MODIFY COLUMN锛屽拷鐣ワ紱
        # 娴嬭瘯鍦烘櫙涓嬭〃浼氳閲嶆柊 create_all
        pass


async def _sync_member_center_prd_v1_aligned(conn: AsyncConnection) -> None:
    """[浼氬憳涓績 PRD v1.0 缁堢瀵归綈 2026-05-26] 鐗╃悊鍒犻櫎/鏂板鑰佸瓧娈碉紝涓ユ牸瀵归綈 PRD v1.0 瀛楁闆嗐€?
    membership_plans锛?      鏂板: is_recommended / max_managed_by / ai_outbound_call_count / price_month / price_year
      杩佺Щ: ai_remind_quota 鈫?ai_outbound_call_count
             ai_alert_quota  鈫?emergency_ai_call_count
             price_monthly   鈫?price_month
             price_yearly    鈫?price_year
             max_guardians   鈫?max_managed_by
      鐗╃悊鍒犻櫎: plan_code / ai_call_quota / ai_alert_quota / ai_remind_quota / max_guardians /
                 benefits_desc / point_multiplier / price_monthly / price_yearly

    free_member_quota锛?      鏂板: max_managed_by / ai_outbound_call_count
      杩佺Щ: ai_remind_quota 鈫?ai_outbound_call_count
             max_guardians   鈫?max_managed_by锛堟敞锛歅RD 鍐崇瓥 9-10锛屽苟闈炲畧鎶や粬浜猴級
      鐗╃悊鍒犻櫎: ai_call_quota / ai_alert_quota / ai_remind_quota / max_guardians / benefits_desc

    discount_rate 鏀逛负 NULLABLE锛沬s_active 榛樿鍊兼敼涓?1 涓嶅彉锛沬s_recommended 榛樿 0銆?    骞傜瓑鎵ц锛氭瘡涓?ALTER 鎿嶄綔鍓嶉兘妫€鏌ュ垪瀛樺湪鎬с€?    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        mp_cols = (
            {col["name"] for col in inspector.get_columns("membership_plans")}
            if "membership_plans" in tables else set()
        )
        fmq_cols = (
            {col["name"] for col in inspector.get_columns("free_member_quota")}
            if "free_member_quota" in tables else set()
        )
        mp_indexes = (
            [idx for idx in inspector.get_indexes("membership_plans")]
            if "membership_plans" in tables else []
        )
        mp_uks = (
            [uk for uk in inspector.get_unique_constraints("membership_plans")]
            if "membership_plans" in tables else []
        )
        return tables, mp_cols, fmq_cols, mp_indexes, mp_uks

    tables, mp_cols, fmq_cols, mp_indexes, mp_uks = await conn.run_sync(_load)

    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€ membership_plans 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    if "membership_plans" in tables:
        # 1. 鍏堟柊澧炴柊鍒楋紙鑻ヤ笉瀛樺湪锛?        if "is_recommended" not in mp_cols:
            await conn.execute(text(
                "ALTER TABLE membership_plans ADD COLUMN is_recommended TINYINT(1) NOT NULL DEFAULT 0 "
                "COMMENT '[PRD v1.0] 鏄惁鎺ㄨ崘濂楅锛堥噾鑹叉弿杈?瑙掓爣锛?"
            ))
        if "max_managed_by" not in mp_cols:
            await conn.execute(text(
                "ALTER TABLE membership_plans ADD COLUMN max_managed_by INT NOT NULL DEFAULT 3 "
                "COMMENT '[PRD v1.0] 琚鐞嗕汉鏁颁笂闄?"
            ))
        if "ai_outbound_call_count" not in mp_cols:
            await conn.execute(text(
                "ALTER TABLE membership_plans ADD COLUMN ai_outbound_call_count INT NOT NULL DEFAULT 0 "
                "COMMENT '[PRD v1.0] AI 澶栧懠鎻愰啋锛堟/鏈堬級锛?1=涓嶉檺'"
            ))
        if "price_month" not in mp_cols:
            await conn.execute(text(
                "ALTER TABLE membership_plans ADD COLUMN price_month DECIMAL(10,2) NULL "
                "COMMENT '[PRD v1.0] 鏈堜环锛?0澶╋級锛孨ULL=涓嶆敮鎸佹湀璐?"
            ))
        if "price_year" not in mp_cols:
            await conn.execute(text(
                "ALTER TABLE membership_plans ADD COLUMN price_year DECIMAL(10,2) NULL "
                "COMMENT '[PRD v1.0] 骞翠环锛?65澶╋級锛孨ULL=涓嶆敮鎸佸勾璐?"
            ))
        if "description" not in mp_cols:
            await conn.execute(text(
                "ALTER TABLE membership_plans ADD COLUMN description VARCHAR(255) NULL "
                "COMMENT '[PRD v1.0] 濂楅璇存槑'"
            ))

        # 2. 鏁版嵁杩佺Щ锛堝湪鍒犻櫎鑰佸垪涔嬪墠锛?        if "ai_remind_quota" in mp_cols:
            await conn.execute(text(
                "UPDATE membership_plans SET ai_outbound_call_count = COALESCE(ai_remind_quota, 0) "
                "WHERE ai_outbound_call_count = 0"
            ))
        if "ai_alert_quota" in mp_cols:
            await conn.execute(text(
                "UPDATE membership_plans SET emergency_ai_call_count = COALESCE(ai_alert_quota, emergency_ai_call_count, 0) "
                "WHERE emergency_ai_call_count = 0 AND ai_alert_quota IS NOT NULL AND ai_alert_quota > 0"
            ))
        if "price_monthly" in mp_cols:
            await conn.execute(text(
                "UPDATE membership_plans SET price_month = price_monthly WHERE price_month IS NULL"
            ))
        if "price_yearly" in mp_cols:
            await conn.execute(text(
                "UPDATE membership_plans SET price_year = price_yearly WHERE price_year IS NULL"
            ))
        if "max_guardians" in mp_cols and "max_managed_by" in (mp_cols | {"max_managed_by"}):
            # PRD v1.0 鍐崇瓥 9-10锛歮ax_managed_by = 琚鐞嗕汉鏁颁笂闄愶紱max_guardians 鍘嗗彶鏄?瀹堟姢浠栦汉/琚畧鎶?锛?            # 杩欓噷鎶婅€佺殑 max_guardians 鏁版嵁杩佸埌 max_managed_by 浣滃厹搴曪紙閬垮厤鏁版嵁涓㈠け锛夈€?            await conn.execute(text(
                "UPDATE membership_plans SET max_managed_by = COALESCE(max_guardians, max_managed_by, 3) "
                "WHERE max_managed_by = 3"
            ))

        # 3. 鍒犻櫎鍞竴绱㈠紩 plan_code锛堝鏈夛級
        for uk in mp_uks:
            uk_name = uk.get("name")
            if uk_name and ("plan_code" in (uk.get("column_names") or []) or uk_name == "uk_membership_plan_code"):
                try:
                    await conn.execute(text(f"ALTER TABLE membership_plans DROP INDEX {uk_name}"))
                except Exception:
                    pass

        # 4. 鐗╃悊鍒犻櫎搴熷純鍒?        drop_cols_mp = [
            "plan_code", "ai_call_quota", "ai_alert_quota", "ai_remind_quota",
            "max_guardians", "benefits_desc", "point_multiplier",
            "price_monthly", "price_yearly",
        ]
        for col in drop_cols_mp:
            if col in mp_cols:
                try:
                    await conn.execute(text(f"ALTER TABLE membership_plans DROP COLUMN {col}"))
                except Exception:
                    # 瀹归敊锛氭煇浜?DB 寮曟搸涓嶆敮鎸?DROP COLUMN锛涙祴璇曠敤 SQLite 浼氬拷鐣?                    pass

        # 5. discount_rate 鏀逛负 NULLABLE
        try:
            await conn.execute(text(
                "ALTER TABLE membership_plans MODIFY COLUMN discount_rate FLOAT NULL "
                "COMMENT '[PRD v1.0] 鍟嗗煄鎶樻墸鐜囷紙0.0~1.0锛孨ULL=鏃犳姌鎵ｏ級'"
            ))
        except Exception:
            pass

    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€ free_member_quota 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    if "free_member_quota" in tables:
        if "max_managed_by" not in fmq_cols:
            await conn.execute(text(
                "ALTER TABLE free_member_quota ADD COLUMN max_managed_by INT NOT NULL DEFAULT 3 "
                "COMMENT '[PRD v1.0] 琚鐞嗕汉鏁颁笂闄?"
            ))
        if "ai_outbound_call_count" not in fmq_cols:
            await conn.execute(text(
                "ALTER TABLE free_member_quota ADD COLUMN ai_outbound_call_count INT NOT NULL DEFAULT 5 "
                "COMMENT '[PRD v1.0] AI 澶栧懠鎻愰啋锛堟/鏈堬級'"
            ))

        if "ai_remind_quota" in fmq_cols:
            await conn.execute(text(
                "UPDATE free_member_quota SET ai_outbound_call_count = COALESCE(ai_remind_quota, 5) "
                "WHERE ai_outbound_call_count = 5"
            ))
        if "max_guardians" in fmq_cols:
            await conn.execute(text(
                "UPDATE free_member_quota SET max_managed_by = COALESCE(max_guardians, 3) "
                "WHERE max_managed_by = 3"
            ))

        drop_cols_fmq = [
            "ai_call_quota", "ai_alert_quota", "ai_remind_quota",
            "max_guardians", "benefits_desc",
        ]
        for col in drop_cols_fmq:
            if col in fmq_cols:
                try:
                    await conn.execute(text(f"ALTER TABLE free_member_quota DROP COLUMN {col}"))
                except Exception:
                    pass

    # 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€ user_quota_usage锛堝琛ㄥ瓨鍦級鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    def _load_uqu(sync_conn):
        inspector = inspect(sync_conn)
        if "user_quota_usage" not in inspector.get_table_names():
            return None
        return {col["name"] for col in inspector.get_columns("user_quota_usage")}

    uqu_cols = await conn.run_sync(_load_uqu)
    if uqu_cols is not None:
        if "ai_outbound_call_used" not in uqu_cols:
            try:
                await conn.execute(text(
                    "ALTER TABLE user_quota_usage ADD COLUMN ai_outbound_call_used INT NOT NULL DEFAULT 0"
                ))
            except Exception:
                pass
        if "emergency_ai_call_used" not in uqu_cols:
            try:
                await conn.execute(text(
                    "ALTER TABLE user_quota_usage ADD COLUMN emergency_ai_call_used INT NOT NULL DEFAULT 0"
                ))
            except Exception:
                pass
        if "ai_chat_used" in uqu_cols:
            try:
                await conn.execute(text(
                    "UPDATE user_quota_usage SET ai_outbound_call_used = COALESCE(ai_chat_used, 0) "
                    "WHERE ai_outbound_call_used = 0"
                ))
                await conn.execute(text("ALTER TABLE user_quota_usage DROP COLUMN ai_chat_used"))
            except Exception:
                pass
        if "ai_phone_alert_used" in uqu_cols:
            try:
                await conn.execute(text("ALTER TABLE user_quota_usage DROP COLUMN ai_phone_alert_used"))
            except Exception:
                pass


async def _sync_decouple_points_mall_from_products_v1(conn: AsyncConnection) -> None:
    """[瀹炵墿鍟嗗搧涓庣Н鍒嗗晢鍩庡交搴曡В鑰?v1.0 2026-05-25]

    灏?products 琛ㄤ腑 points_exchangeable / points_price 涓ゅ垪**缃┖锛堟竻闆讹級**锛?    浣挎墍鏈夊巻鍙?瀹炵墿鍟嗗搧 + 杩涘叆绉垎鍟嗗煄 = 鏄?閰嶇疆鑷劧澶辨晥銆?
    鎸?PRD v1.0 绗竷鑺?鍥炴粴棰勬"锛屾湰娆?*鍙疆绌恒€佷笉鐗╃悊 DROP COLUMN**锛?    淇濈暀鐗╃悊鍒椾竴涓彂鐗堝懆鏈熶綔涓哄洖婊氱紦鍐诧紱涓嬩釜杩唬鍐嶅喅瀹氭槸鍚︾墿鐞嗗垹闄ゃ€?
    骞傜瓑锛氬彲浠ュ娆℃墽琛岋紱澶氭鎵ц鍙細閲嶅 UPDATE 0 琛岋紙鎴栦笉鍙橈級銆?    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "products" not in tables:
            return set()
        return {col["name"] for col in inspector.get_columns("products")}

    product_cols = await conn.run_sync(_load)
    if not product_cols:
        return

    if "points_exchangeable" in product_cols:
        await conn.execute(text(
            "UPDATE products SET points_exchangeable = 0 WHERE points_exchangeable = 1"
        ))
    if "points_price" in product_cols:
        await conn.execute(text(
            "UPDATE products SET points_price = 0 WHERE points_price IS NOT NULL AND points_price <> 0"
        ))


async def _sync_guardian_bugfix_v1(conn: AsyncConnection) -> None:
    """[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] 瀹堟姢浜轰綋绯?Bug 淇锛?
    1. family_invitations 鏂板 nickname 瀛楁锛圢OT NULL DEFAULT ''锛?    2. family_management.status 鍏煎 cancelled_by_target 鏂版灇涓撅紙VARCHAR 鍒楀凡瀛橈紝鏃犻渶 DDL锛?    3. 鍘嗗彶鎮┖ pending 閭€璇?nickname 鍥炲～涓?'寰呮縺娲绘垚鍛?
    """
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        cols_inv: set[str] = set()
        if "family_invitations" in tables:
            cols_inv = {c["name"] for c in inspector.get_columns("family_invitations")}
        return tables, cols_inv

    tables, cols_inv = await conn.run_sync(_load)
    if "family_invitations" not in tables:
        return

    if "nickname" not in cols_inv:
        await conn.execute(text(
            "ALTER TABLE family_invitations ADD COLUMN nickname VARCHAR(50) NOT NULL DEFAULT ''"
        ))
        # 鍥炲～鍘嗗彶鎮┖ pending 閭€璇风殑 nickname
        await conn.execute(text(
            "UPDATE family_invitations SET nickname='寰呮縺娲绘垚鍛? "
            "WHERE (nickname IS NULL OR nickname='') "
            "AND member_id IS NULL AND status='pending'"
        ))


async def _sync_home_safety_v2(conn: AsyncConnection) -> None:
    """[PRD-HOME-SAFETY-V2 2026-05-27] 鎵╁睍 home_safety_callback_config / home_safety_alarm 瀛楁锛屾柊寤?push_history / callback_log銆?""
    def _load_v2(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        cfg_cols = (
            {c["name"] for c in inspector.get_columns("home_safety_callback_config")}
            if "home_safety_callback_config" in tables else None
        )
        alarm_cols = (
            {c["name"] for c in inspector.get_columns("home_safety_alarm")}
            if "home_safety_alarm" in tables else None
        )
        return tables, cfg_cols, alarm_cols

    tables, cfg_cols, alarm_cols = await conn.run_sync(_load_v2)

    # home_safety_callback_config 鎵╁瓧娈?    if cfg_cols is not None:
        if "upstream_path" not in cfg_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_config ADD COLUMN upstream_path VARCHAR(256) NULL"))
        if "callback_domain" not in cfg_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_config ADD COLUMN callback_domain VARCHAR(256) NULL"))
        if "callback_path" not in cfg_cols:
            await conn.execute(text(
                "ALTER TABLE home_safety_callback_config ADD COLUMN callback_path VARCHAR(256) NULL DEFAULT '/api/home_safety/callback/alarm'"
            ))
        if "last_push_status" not in cfg_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_config ADD COLUMN last_push_status VARCHAR(16) NULL"))
        if "last_push_url" not in cfg_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_config ADD COLUMN last_push_url VARCHAR(512) NULL"))
        if "last_push_code" not in cfg_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_config ADD COLUMN last_push_code INT NULL"))
        if "last_push_message" not in cfg_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_config ADD COLUMN last_push_message VARCHAR(512) NULL"))
        if "last_push_raw" not in cfg_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_config ADD COLUMN last_push_raw TEXT NULL"))
        # [BUGFIX HS-V2-ALTER 2026-05-28] 鎺ㄩ€佸垽瀹氫緷鎹瓧娈碉紙鐢ㄤ簬 UI 鎮诞鎻愮ず锛?        if "last_push_judge_basis" not in cfg_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_config ADD COLUMN last_push_judge_basis TEXT NULL"))
        def _check_token_col(sync_conn):
            inspector = inspect(sync_conn)
            for col in inspector.get_columns("home_safety_callback_config"):
                if col["name"] == "auth_token":
                    return str(col["type"]).upper()
            return ""
        token_type = await conn.run_sync(_check_token_col)
        if token_type and "TEXT" not in token_type and "VARCHAR" in token_type:
            try:
                await conn.execute(text("ALTER TABLE home_safety_callback_config MODIFY COLUMN auth_token TEXT NULL"))
            except Exception:
                pass

    # home_safety_alarm 鎵╁瓧娈?    if alarm_cols is not None:
        if "vendor_msg_id" not in alarm_cols:
            await conn.execute(text("ALTER TABLE home_safety_alarm ADD COLUMN vendor_msg_id VARCHAR(64) NULL"))
            try:
                await conn.execute(text("CREATE UNIQUE INDEX uq_hs_alarm_vendor_msg_id ON home_safety_alarm (vendor_msg_id)"))
            except Exception:
                pass
        if "gw_id" not in alarm_cols:
            await conn.execute(text("ALTER TABLE home_safety_alarm ADD COLUMN gw_id VARCHAR(64) NULL"))
        if "dev_name" not in alarm_cols:
            await conn.execute(text("ALTER TABLE home_safety_alarm ADD COLUMN dev_name VARCHAR(128) NULL"))
        if "call_type" not in alarm_cols:
            await conn.execute(text("ALTER TABLE home_safety_alarm ADD COLUMN call_type INT NULL"))
        if "data_type" not in alarm_cols:
            await conn.execute(text("ALTER TABLE home_safety_alarm ADD COLUMN data_type VARCHAR(32) NULL"))
        if "notify_ai_call_status" not in alarm_cols:
            await conn.execute(text(
                "ALTER TABLE home_safety_alarm ADD COLUMN notify_ai_call_status VARCHAR(16) NOT NULL DEFAULT 'failed'"
            ))
        if "notify_ai_call_fail_reason" not in alarm_cols:
            await conn.execute(text(
                "ALTER TABLE home_safety_alarm ADD COLUMN notify_ai_call_fail_reason VARCHAR(256) NULL DEFAULT '鏈湡鏈鎺ュ鍛奸€氶亾'"
            ))
        if "source_ip" not in alarm_cols:
            await conn.execute(text("ALTER TABLE home_safety_alarm ADD COLUMN source_ip VARCHAR(64) NULL"))

    # 鏂拌〃 home_safety_callback_push_history / home_safety_callback_log 鐢?metadata.create_all 鍒涘缓

    # [BUGFIX HS-V2-ALTER 2026-05-28] home_safety_callback_log 琛ㄥ凡瀛樺湪鏃惰ˉ榻愬璁″瓧娈碉紝
    # 閬垮厤 SELECT 鍛戒腑 ORM 鏂板瓧娈典絾搴撳唴鏃犲搴斿垪瀵艰嚧 1054 Unknown column / HTTP 500銆?    def _load_log_cols(sync_conn):
        inspector = inspect(sync_conn)
        if "home_safety_callback_log" not in set(inspector.get_table_names()):
            return None
        return {c["name"] for c in inspector.get_columns("home_safety_callback_log")}

    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] home_safety_device_binding 鎵╁瓧娈?    def _load_binding_cols(sync_conn):
        inspector = inspect(sync_conn)
        if "home_safety_device_binding" not in set(inspector.get_table_names()):
            return None
        return {c["name"] for c in inspector.get_columns("home_safety_device_binding")}

    bind_cols = await conn.run_sync(_load_binding_cols)
    if bind_cols is not None:
        if "emergency_phone" not in bind_cols:
            await conn.execute(text(
                "ALTER TABLE home_safety_device_binding ADD COLUMN emergency_phone VARCHAR(11) NULL"
            ))
        if "invalid_reason" not in bind_cols:
            await conn.execute(text(
                "ALTER TABLE home_safety_device_binding ADD COLUMN invalid_reason VARCHAR(128) NULL"
            ))
        # 鏀舵暃 gateway_sn 闀垮害锛堜繚鐣?16 浠ュ吋瀹瑰凡鏈?12 浣嶆暟鎹瓨鍦紝浣嗚涔変负 8 浣嶅ぇ鍐欙級
        # 浠呭湪鍘熼暱搴﹀皬浜?16 鏃惰皟鏁达紝閬垮厤鏃犺皳鐨?DDL
        try:
            await conn.execute(text(
                "ALTER TABLE home_safety_device_binding MODIFY COLUMN gateway_sn VARCHAR(16) NOT NULL"
            ))
        except Exception:
            pass

        # 鈹€鈹€ 鏁版嵁杩佺Щ锛氭妸鐜版湁 gateway_sn 鎴柇鍒板墠 8 浣嶅苟杞ぇ鍐欙紱鎾炲彿鍒欎繚鐣欐渶鏂版潯鐩?鈹€鈹€
        # 1) 澶囦唤 dump 鐢遍儴缃茶剼鏈礋璐ｏ紝杩欓噷鍙仛骞傜瓑杩佺Щ
        # 2) 鏀堕泦褰撳墠鎵€鏈?binding 鐨?(id, gateway_sn, updated_at, user_id, device_sn, status)
        try:
            rows_all = (
                await conn.execute(text(
                    "SELECT id, user_id, gateway_sn, device_sn, status, updated_at "
                    "FROM home_safety_device_binding"
                ))
            ).fetchall()
        except Exception:
            rows_all = []

        # 鎶婃瘡鏉¤褰曠殑 gateway_sn 鎴柇涓?8 浣嶅ぇ鍐?        import re as _re
        _norm = lambda s: _re.sub(r"[^A-Z0-9]", "", (s or "").upper())[:8]
        # 鎸?(user_id, normalized_gw) 鍒嗙粍锛屼繚鐣?updated_at 鏈€鏂颁竴鏉′负鏈夋晥锛坰tatus=1锛夛紝鍏跺畠鍘?status=1 鐨勬爣璁?status=2 invalid
        group_map: Dict[Any, List[Any]] = {}
        for r in rows_all:
            try:
                rid, uid, old_gw, dev_sn, st, upd = r[0], r[1], r[2], r[3], r[4], r[5]
            except Exception:
                continue
            new_gw = _norm(old_gw)
            if not new_gw:
                continue
            key = (uid, new_gw, dev_sn)
            group_map.setdefault(key, []).append((rid, st, upd, old_gw, new_gw))

        for key, lst in group_map.items():
            if not lst:
                continue
            # 鍐欏洖鏂?gw锛堟墍鏈夎褰曢兘闇€鏇存柊锛?            for rid, st, upd, old_gw, new_gw in lst:
                try:
                    if old_gw != new_gw:
                        await conn.execute(text(
                            "UPDATE home_safety_device_binding SET gateway_sn=:gw WHERE id=:id"
                        ), {"gw": new_gw, "id": rid})
                except Exception:
                    pass

            # 浠?status=1 鐨勶紙宸茬粦瀹氭湁鏁堬級鏈?鎾炲彿"闂锛泂tatus=0锛堝凡瑙ｇ粦锛変笉鍙備笌鎾炲彿鍒ゅ畾
            actives = [t for t in lst if t[1] == 1]
            if len(actives) <= 1:
                continue
            # 鎸?updated_at 鍊掑簭锛屼繚鐣欑涓€鏉★紝鍏朵綑鏍?invalid锛坰tatus=2锛?            try:
                actives_sorted = sorted(
                    actives,
                    key=lambda t: (t[2] is not None, t[2] if t[2] else 0),
                    reverse=True,
                )
            except Exception:
                actives_sorted = actives
            for idx, item in enumerate(actives_sorted):
                if idx == 0:
                    continue
                rid = item[0]
                try:
                    await conn.execute(text(
                        "UPDATE home_safety_device_binding SET status=2, invalid_reason=:rs WHERE id=:id"
                    ), {
                        "rs": "鍘嗗彶缃戝叧SN鎴柇鎾炲彿锛岃閲嶆柊缁戝畾",
                        "id": rid,
                    })
                except Exception:
                    pass

    # [PRD-HOME-SAFETY-GWID-EPHONE 2026-05-28] home_safety_alarm 鎵╁瓧娈?    def _load_alarm_cols2(sync_conn):
        inspector = inspect(sync_conn)
        if "home_safety_alarm" not in set(inspector.get_table_names()):
            return None
        return {c["name"] for c in inspector.get_columns("home_safety_alarm")}

    alarm_cols2 = await conn.run_sync(_load_alarm_cols2)
    if alarm_cols2 is not None:
        if "device_emergency_phone" not in alarm_cols2:
            await conn.execute(text(
                "ALTER TABLE home_safety_alarm ADD COLUMN device_emergency_phone VARCHAR(11) NULL"
            ))
        if "notify_targets_json" not in alarm_cols2:
            await conn.execute(text(
                "ALTER TABLE home_safety_alarm ADD COLUMN notify_targets_json TEXT NULL"
            ))
        if "notify_dedup_skipped" not in alarm_cols2:
            await conn.execute(text(
                "ALTER TABLE home_safety_alarm ADD COLUMN notify_dedup_skipped INT NULL DEFAULT 0"
            ))
        try:
            await conn.execute(text(
                "ALTER TABLE home_safety_alarm MODIFY COLUMN gateway_sn VARCHAR(16) NULL"
            ))
        except Exception:
            pass

    log_cols = await conn.run_sync(_load_log_cols)
    if log_cols is not None:
        if "request_method" not in log_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_log ADD COLUMN request_method VARCHAR(8) NULL"))
        if "request_url" not in log_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_log ADD COLUMN request_url VARCHAR(512) NULL"))
        if "response_status" not in log_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_log ADD COLUMN response_status INT NULL"))
        if "response_body" not in log_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_log ADD COLUMN response_body TEXT NULL"))
        if "processed_at" not in log_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_log ADD COLUMN processed_at DATETIME NULL"))
        if "device_sn" not in log_cols:
            await conn.execute(text("ALTER TABLE home_safety_callback_log ADD COLUMN device_sn VARCHAR(128) NULL"))
        # [BUGFIX HS-CALLBACK-DATATYPE 2026-05-29] 鏂板 data_type 鍒?+ 鏅€氱储寮?        if "data_type" not in log_cols:
            await conn.execute(text(
                "ALTER TABLE home_safety_callback_log ADD COLUMN data_type VARCHAR(64) NULL"
            ))
            try:
                await conn.execute(text(
                    "ALTER TABLE home_safety_callback_log ADD INDEX idx_hsl_data_type (data_type)"
                ))
            except Exception:
                pass

    # [PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] member_id / migrated_to_self 鎵╁瓧娈?    def _load_bind_cols_v3(sync_conn):
        inspector = inspect(sync_conn)
        if "home_safety_device_binding" not in set(inspector.get_table_names()):
            return None
        return {c["name"] for c in inspector.get_columns("home_safety_device_binding")}

    bind_cols_v3 = await conn.run_sync(_load_bind_cols_v3)
    if bind_cols_v3 is not None:
        if "member_id" not in bind_cols_v3:
            await conn.execute(text(
                "ALTER TABLE home_safety_device_binding ADD COLUMN member_id INT NULL"
            ))
            try:
                await conn.execute(text(
                    "ALTER TABLE home_safety_device_binding ADD INDEX idx_hsdb_member_id (member_id)"
                ))
            except Exception:
                pass
        if "migrated_to_self" not in bind_cols_v3:
            await conn.execute(text(
                "ALTER TABLE home_safety_device_binding ADD COLUMN migrated_to_self TINYINT(1) NOT NULL DEFAULT 0"
            ))
        # [BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 璁惧澶囨敞鍚?        if "remark" not in bind_cols_v3:
            await conn.execute(text(
                "ALTER TABLE home_safety_device_binding ADD COLUMN remark VARCHAR(64) DEFAULT NULL COMMENT '璁惧澶囨敞鍚嶏紝鈮?0瀛楋紝濡傘€岀埜鐖稿銆?"
            ))

    def _load_alarm_cols_v3(sync_conn):
        inspector = inspect(sync_conn)
        if "home_safety_alarm" not in set(inspector.get_table_names()):
            return None
        return {c["name"] for c in inspector.get_columns("home_safety_alarm")}

    alarm_cols_v3 = await conn.run_sync(_load_alarm_cols_v3)
    if alarm_cols_v3 is not None:
        if "member_id" not in alarm_cols_v3:
            await conn.execute(text(
                "ALTER TABLE home_safety_alarm ADD COLUMN member_id INT NULL"
            ))
            try:
                await conn.execute(text(
                    "ALTER TABLE home_safety_alarm ADD INDEX idx_hsa_member_id (member_id)"
                ))
            except Exception:
                pass

    def _load_contact_cols_v3(sync_conn):
        inspector = inspect(sync_conn)
        if "home_safety_emergency_contact" not in set(inspector.get_table_names()):
            return None
        return {c["name"] for c in inspector.get_columns("home_safety_emergency_contact")}

    contact_cols_v3 = await conn.run_sync(_load_contact_cols_v3)
    if contact_cols_v3 is not None:
        if "member_id" not in contact_cols_v3:
            await conn.execute(text(
                "ALTER TABLE home_safety_emergency_contact ADD COLUMN member_id INT NULL"
            ))
            try:
                await conn.execute(text(
                    "ALTER TABLE home_safety_emergency_contact ADD INDEX idx_hsec_member_id (member_id)"
                ))
            except Exception:
                pass


async def _sync_reverse_guardian_invite_name_v1(conn: AsyncConnection) -> None:
    """[PRD-GUARDIAN-CARD-OPTIM-V1 2026-06-02] 鍙嶅悜瀹堟姢閭€璇锋柊澧炪€屽悕瀛椼€嶅瓧娈?guardian_name銆?""
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "reverse_guardian_invitations" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("reverse_guardian_invitations")}

    columns = await conn.run_sync(_load)
    if columns is None:
        return
    if "guardian_name" not in columns:
        await conn.execute(text(
            "ALTER TABLE reverse_guardian_invitations ADD COLUMN guardian_name VARCHAR(50) NULL"
        ))


async def _sync_health_checkin_items_v1(conn: AsyncConnection) -> None:
    """[PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] health_checkin_items 鏂板 start_date / end_date / weekly_target_count"""
    def _load(sync_conn):
        inspector = inspect(sync_conn)
        tables = set(inspector.get_table_names())
        if "health_checkin_items" not in tables:
            return None
        return {col["name"] for col in inspector.get_columns("health_checkin_items")}

    cols = await conn.run_sync(_load)
    if cols is None:
        return
    if "start_date" not in cols:
        try:
            await conn.execute(text("ALTER TABLE health_checkin_items ADD COLUMN start_date DATE NULL"))
        except Exception as e:
            print(f"[schema_sync] health_checkin_items.start_date add warn: {e}")
    if "end_date" not in cols:
        try:
            await conn.execute(text("ALTER TABLE health_checkin_items ADD COLUMN end_date DATE NULL"))
        except Exception as e:
            print(f"[schema_sync] health_checkin_items.end_date add warn: {e}")
    if "weekly_target_count" not in cols:
        try:
            await conn.execute(text("ALTER TABLE health_checkin_items ADD COLUMN weekly_target_count INT NULL"))
        except Exception as e:
            print(f"[schema_sync] health_checkin_items.weekly_target_count add warn: {e}")


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
    await _sync_chat_session_idle_archive_v1(conn)
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
    await _sync_cards_v2_fields(conn)
    await _migrate_store_codes(conn)
    # [PRD 璁㈠崟鐘舵€佹満绠€鍖栨柟妗?v1.0] 涓€鍒€鍒囪縼绉绘墍鏈?appointed 鈫?pending_use
    await _migrate_appointed_to_pending_use(conn)
    # [PRD 鍟嗗 PC 鍚庡彴浼樺寲 v1.1 路 F7] 涓€娆℃€ф暟鎹縼绉伙細redeemed 鈫?completed
    await _migrate_redeemed_to_completed(conn)
    # [涓婇棬鏈嶅姟灞ョ害 PRD v1.0] on_site 灞ョ害绫诲瀷 + 涓婇棬鍦板潃瀛楁
    await _sync_on_site_fulfillment(conn)
    # [鏀粯閰嶇疆 PRD v1.0] payment_channels 琛?+ 4 鏉＄瀛?+ orders/unified_orders 鍔犲垪
    await _sync_payment_config(conn)
    # [鏍搁攢璁㈠崟杩囨湡+鏀规湡瑙勫垯浼樺寲 v1.0] products.allow_reschedule + unified_orders.reschedule_*
    await _sync_reschedule_columns(conn)
    # [PRD-469 v2 P0] medication_reminders 鏂板瀛楁
    await _sync_medication_reminders_prd469_v2(conn)
    # [PRD-MED-PLAN-V1 2026-05-16] reminder_settings 澧炲姞 medication_ai_call_enabled
    await _sync_reminder_settings_med_v1(conn)
    # [PRD-FAMILY-GUARDIAN-V1 2026-05-18] 瀹跺涵浣撴寮傚父瀹堟姢鎺ㄩ€侊細琛ㄤ笌瀛楁
    await _sync_family_guardian_v1(conn)
    # [PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] guardian_ai_call_settings 琛ㄥ垱寤猴紙鎸?owner+target 鍞竴锛?    await _sync_guardian_ai_call_settings_v1(conn)
    # [PRD-HEALTH-ARCHIVE-OPTIM-V2 2026-05-18] family_members 鏂板 avatar_color_index/ai_call_enabled/ai_call_timing/guardian_alert_minutes
    await _sync_family_members_archive_optim_v2(conn)
    # [浠樿垂浼氬憳浣撶郴 PRD v1.1 2026-05-24] membership_plans / user_memberships / free_member_quota + products.is_member_discount_eligible
    await _sync_membership_v1(conn)
    # [瀹堟姢浜轰綋绯?PRD v1.1 2026-05-25] family_management 瀛楁 + 杞Щ璇锋眰琛?+ 鍛婅棰濆害浣跨敤琛?    await _sync_guardian_system_v1(conn)
    # [瀹堟姢浜轰綋绯?PRD v1.2 2026-05-25] membership_plans 鏂板瓧娈?+ 浠ｄ粯寮€鍏宠〃 + 绱ф€ュ懠鍙Е鍙戞簮琛?+ AI 澶栧懠鎻愰啋琛?    await _sync_guardian_system_v12(conn)
    # [瀹炵墿鍟嗗搧涓庣Н鍒嗗晢鍩庡交搴曡В鑰?v1.0 2026-05-25] 缃┖ products.points_exchangeable / points_price
    await _sync_decouple_points_mall_from_products_v1(conn)
    # [鍋ュ悍璁″垝绠＄悊鑿滃崟涓嬬嚎涓庢墦鍗＄粺璁℃惉瀹?v1.0 2026-05-25] DROP TABLE default_health_tasks
    await _sync_drop_default_health_tasks_v1(conn)
    # [浼氬憳涓績浼樺寲 PRD v2.0 2026-05-26] order_items 鏂板 membership_plan_id / membership_period 鍒?    await _sync_member_center_v2(conn)
    # [浼氬憳涓績 PRD v1.0 缁堢瀵归綈 2026-05-26] membership_plans / free_member_quota 瀛楁閲嶅懡鍚?+ 鐗╃悊鍒犻櫎鑰佸垪
    await _sync_member_center_prd_v1_aligned(conn)
    # [PRD-HOME-SAFETY-V2 2026-05-27] 灞呭瀹夊叏璁惧澶栭儴 API 瀵规帴 v2锛氭墿瀛楁 + 鏂拌〃
    await _sync_home_safety_v2(conn)
    # [BUGFIX-GUARDIAN-LIST-CONSISTENCY-V1 2026-05-29] family_invitations.nickname 瀛楁 + cancelled_by_target 鐘舵€佸吋瀹?    await _sync_guardian_bugfix_v1(conn)
    # [PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] max_managed 瀛楁鍙ｅ緞鐢便€屼笉鍚湰浜恒€嶆敼涓恒€屽惈鏈汉銆嶏紝涓€娆℃€?+1 鏁版嵁杩佺Щ
    await _sync_membership_v11_max_managed_include_self_migration(conn)
    await _sync_reverse_guardian_invite_name_v1(conn)
    # [PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] health_checkin_items 鏂板 start_date / end_date / weekly_target_count
    await _sync_health_checkin_items_v1(conn)
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
