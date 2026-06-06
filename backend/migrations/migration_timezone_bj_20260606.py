"""
日期时区简化优化方案：数据库迁移 Python 脚本
目标：所有时间字段从 UTC 统一加 8 小时转为北京时间
生成日期：2026-06-06
注意：此脚本应仅在低峰期执行，建议先备份数据库

用法：
    python migration_timezone_bj_20260606.py          # dry_run=True（默认，仅打印 SQL）
    python migration_timezone_bj_20260606.py --go      # 实际执行
"""
import os
import sys
from typing import List, Tuple

import asyncio

# 数据库连接信息（可通过环境变量覆盖）
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "bini_health")

# ────────────── 所有需要迁移的表与时间字段 ──────────────

TIME_FIELDS: List[Tuple[str, List[str]]] = [
    ("users", ["created_at", "updated_at", "last_login_at", "deleted_at"]),
    ("relation_types", ["created_at", "updated_at"]),
    ("family_members", ["created_at", "status_changed_at"]),
    ("verification_codes", ["created_at", "expires_at"]),
    ("account_identities", ["created_at", "updated_at"]),
    ("merchant_profiles", ["created_at", "updated_at"]),
    ("merchant_stores", ["created_at", "updated_at"]),
    ("merchant_store_memberships", ["created_at", "updated_at"]),
    ("merchant_store_permissions", ["created_at"]),
    ("merchant_notifications", ["created_at"]),
    ("merchant_order_verifications", ["verified_at"]),
    ("merchant_categories", ["created_at", "updated_at"]),
    ("merchant_role_templates", ["created_at", "updated_at"]),
    ("order_attachments", ["created_at", "deleted_at"]),
    ("merchant_business_hours", ["created_at", "updated_at"]),
    ("merchant_invoice_profiles", ["created_at", "updated_at"]),
    ("settlement_statements", ["created_at", "updated_at", "confirmed_at", "settled_at"]),
    ("settlement_payment_proofs", ["created_at", "updated_at", "paid_at"]),
    ("merchant_export_tasks", ["created_at", "finished_at"]),
    ("health_profiles", ["created_at", "updated_at"]),
    ("disease_presets", ["created_at", "updated_at"]),
    ("allergy_records", ["created_at"]),
    ("medical_histories", ["created_at"]),
    ("family_medical_histories", ["created_at"]),
    ("medication_records", ["created_at"]),
    ("visit_records", ["created_at"]),
    ("checkup_reports", ["created_at", "share_expires_at"]),
    ("checkup_indicators", ["created_at"]),
    ("chat_sessions", ["created_at", "updated_at", "last_active_at", "archived_at", "pinned_at"]),
    ("chat_messages", ["created_at"]),
    ("tcm_configs", ["created_at", "updated_at"]),
    ("tcm_diagnoses", ["created_at"]),
    ("constitution_answers", ["created_at"]),
    ("constitution_content_configs", ["created_at", "updated_at"]),
    ("service_categories", ["created_at"]),
    ("service_items", ["created_at", "updated_at"]),
    ("orders", ["created_at", "updated_at", "verified_at"]),
    ("order_reviews", ["created_at"]),
    ("experts", ["created_at"]),
    ("expert_schedules", ["created_at"]),
    ("appointments", ["created_at"]),
    ("points_records", ["created_at"]),
    ("member_levels", ["created_at"]),
    ("sign_in_records", ["created_at"]),
    ("points_mall_items", ["created_at"]),
    ("points_mall_goods_change_log", ["created_at"]),
    ("points_exchanges", ["created_at"]),
    ("point_exchange_records", ["created_at", "updated_at", "exchange_time", "expire_at", "used_at"]),
    ("health_plans", ["created_at"]),
    ("health_tasks", ["created_at"]),
    ("task_check_ins", ["created_at"]),
    ("articles", ["created_at", "updated_at"]),
    ("article_categories", ["created_at"]),
    ("news", ["created_at", "updated_at"]),
    ("news_tag_history", ["last_used_at"]),
    ("comments", ["created_at"]),
    ("favorites", ["created_at"]),
    ("notifications", ["created_at", "read_at"]),
    ("system_configs", ["created_at", "updated_at"]),
    ("payment_channels", ["created_at", "updated_at", "last_test_at"]),
    ("ai_model_templates", ["created_at", "updated_at"]),
    ("ai_model_configs", ["created_at", "updated_at", "template_synced_at", "last_test_time"]),
    ("sms_configs", ["created_at", "updated_at"]),
    ("sms_logs", ["created_at"]),
    ("sms_templates", ["created_at", "updated_at"]),
    ("email_logs", ["created_at"]),
    ("customer_service_sessions", ["created_at", "updated_at"]),
    ("customer_service_messages", ["created_at"]),
    ("knowledge_bases", ["created_at", "updated_at"]),
    ("knowledge_entries", ["created_at", "updated_at", "last_hit_at"]),
    ("knowledge_entry_products", ["created_at"]),
    ("knowledge_search_configs", ["created_at", "updated_at"]),
    ("knowledge_fallback_configs", ["created_at", "updated_at"]),
    ("knowledge_scene_bindings", ["created_at"]),
    ("knowledge_hit_logs", ["created_at"]),
    ("knowledge_missed_questions", ["created_at", "updated_at"]),
    ("knowledge_import_tasks", ["created_at", "updated_at"]),
    ("ai_sensitive_words", ["created_at", "updated_at"]),
    ("ai_prompt_configs", ["updated_at"]),
    ("ai_disclaimer_configs", ["updated_at"]),
    ("cos_configs", ["created_at", "updated_at"]),
    ("cos_files", ["created_at"]),
    ("cos_migration_tasks", ["created_at", "started_at", "completed_at"]),
    ("cos_migration_details", ["migrated_at"]),
    ("ocr_configs", ["created_at", "updated_at"]),
    ("ocr_provider_configs", ["created_at", "updated_at"]),
    ("ocr_scene_templates", ["created_at", "updated_at"]),
    ("ocr_call_records", ["created_at"]),
    ("ocr_upload_configs", ["updated_at"]),
    ("report_alerts", ["created_at"]),
    ("checkup_report_details", ["created_at"]),
    ("drug_identify_details", ["created_at"]),
    ("chat_share_records", ["created_at"]),
    ("prompt_templates", ["created_at", "updated_at"]),
    ("prompt_type_config", ["created_at", "updated_at"]),
    ("share_links", ["created_at"]),
    ("home_menu_items", ["created_at", "updated_at"]),
    ("home_banners", ["created_at", "updated_at"]),
    ("search_histories", ["created_at", "updated_at"]),
    ("search_hot_words", ["created_at", "updated_at"]),
    ("search_recommend_words", ["created_at", "updated_at"]),
    ("search_block_words", ["created_at"]),
    ("search_logs", ["created_at"]),
    ("home_notices", ["created_at", "updated_at", "start_time", "end_time"]),
    ("bottom_nav_config", ["created_at", "updated_at"]),
    ("medication_reminders", ["created_at"]),
    ("medication_check_ins", ["created_at", "check_in_time"]),
    ("health_checkin_items", ["created_at"]),
    ("health_checkin_records", ["created_at", "check_in_time"]),
    ("plan_template_categories", ["created_at"]),
    ("recommended_plans", ["created_at"]),
    ("recommended_plan_tasks", ["created_at"]),
    ("user_plans", ["created_at"]),
    ("user_plan_tasks", ["created_at"]),
    ("user_plan_task_records", ["created_at", "check_in_time"]),
    ("notification_logs", ["created_at"]),
    ("cities", ["created_at", "updated_at"]),
    ("chat_function_buttons", ["created_at", "updated_at"]),
    ("questionnaire_template", ["created_at", "updated_at"]),
    ("questionnaire_question", ["created_at", "updated_at"]),
    ("questionnaire_classification_rule", ["created_at", "updated_at"]),
    ("questionnaire_recommendation", ["created_at", "updated_at"]),
    ("questionnaire_answer", ["created_at", "completed_at", "ai_generated_at"]),
    ("tags", ["created_at", "updated_at"]),
    ("goods_tags", ["created_at"]),
    ("questionnaire_recommend_config", ["created_at", "updated_at"]),
    ("body_part_dict", ["created_at", "updated_at"]),
    ("health_check_template", ["created_at", "updated_at"]),
    ("digital_humans", ["created_at", "updated_at"]),
    ("voice_call_records", ["created_at", "start_time", "end_time"]),
    ("voice_service_configs", ["created_at", "updated_at"]),
    ("family_management", ["created_at", "cancelled_at"]),
    ("family_invitations", ["created_at", "expires_at", "accepted_at"]),
    ("management_operation_logs", ["created_at"]),
    ("system_messages", ["created_at", "read_at"]),
    ("product_categories", ["created_at", "updated_at"]),
    ("appointment_forms", ["created_at", "updated_at"]),
    ("appointment_form_fields", ["created_at", "updated_at"]),
    ("products", ["created_at", "updated_at"]),
    ("product_skus", ["created_at", "updated_at"]),
    ("product_stores", ["created_at"]),
    ("user_addresses", ["created_at", "updated_at"]),
    ("coupons", ["created_at", "updated_at", "valid_start", "valid_end", "offline_at"]),
    ("user_coupons", ["created_at", "used_at", "expire_at"]),
    ("coupon_grants", ["granted_at", "used_at"]),
    ("coupon_code_batches", ["created_at", "expire_at", "voided_at"]),
    ("coupon_redeem_codes", ["created_at", "sold_at", "used_at", "voided_at"]),
    ("coupon_op_logs", ["created_at"]),
    ("partners", ["created_at", "updated_at"]),
    ("audit_phones", ["created_at", "updated_at"]),
    ("audit_requests", ["created_at", "updated_at", "approved_at"]),
    ("audit_codes", ["created_at", "expires_at"]),
    ("audit_lockouts", ["last_fail_at"]),
    ("unified_orders", ["created_at", "updated_at", "paid_at", "shipped_at",
                        "received_at", "completed_at", "cancelled_at", "store_confirmed_at"]),
    ("order_items", ["created_at", "updated_at", "appointment_time"]),
    ("order_redemptions", ["created_at", "redeemed_at"]),
    ("member_qr_tokens", ["created_at", "expires_at"]),
    ("checkin_records", ["created_at", "checked_in_at"]),
    ("store_visit_records", ["created_at", "visited_at"]),
    ("refund_requests", ["created_at", "updated_at"]),
    ("video_consult_config", ["created_at", "updated_at"]),
    ("user_feedback", ["created_at", "updated_at"]),
    ("app_settings", ["updated_at"]),
    ("user_health_profiles", ["created_at", "updated_at"]),
    ("staff_wechat_bindings", ["created_at", "bound_at"]),
    ("order_notes", ["created_at"]),
    ("order_appointment_logs", ["created_at"]),
    ("map_config", ["created_at", "updated_at"]),
    ("map_test_logs", ["created_at"]),
    ("card_definitions", ["created_at", "updated_at"]),
    ("card_items", ["created_at"]),
    ("user_cards", ["created_at", "updated_at", "valid_from", "valid_to"]),
    ("card_usage_logs", ["created_at", "used_at"]),
    ("card_redemption_codes", ["created_at", "issued_at", "expires_at", "used_at"]),
    ("merchant_calendar_views", ["created_at", "updated_at"]),
    ("booking_notification_logs", ["created_at"]),
    ("ai_home_config_logs", ["created_at"]),
    ("medication_plans", ["created_at", "updated_at"]),
    ("medication_logs", ["checked_at"]),
    ("medication_library", ["created_at", "updated_at"]),
    ("medication_library_pending", ["created_at", "updated_at", "last_hit_at", "operated_at"]),
    ("health_info_extra", ["created_at", "updated_at"]),
    ("health_events", ["created_at", "updated_at"]),
    ("device_scene_group", ["created_at", "updated_at"]),
    ("device_bindings", ["created_at", "updated_at", "bound_at", "last_sync_at"]),
    ("reminder_settings", ["created_at", "updated_at"]),
    ("guardian_ai_call_settings", ["created_at", "updated_at"]),
    ("medical_record_cards", ["created_at", "updated_at"]),
    ("ai_call_membership_levels", ["created_at", "updated_at"]),
    ("ai_call_global_config", ["created_at", "updated_at"]),
    ("user_memberships", ["created_at", "updated_at"]),
    ("ai_call_logs", ["created_at", "call_at"]),
    ("abnormal_thresholds", ["created_at", "updated_at"]),
    ("alert_message_templates", ["created_at", "updated_at"]),
    ("family_alert_logs", ["pushed_at", "clicked_at"]),
    ("virtual_member_migrations", ["created_at", "confirmed_at"]),
    ("health_reminders", ["created_at", "updated_at", "completed_at"]),
    ("health_alert_notifications", ["created_at", "sent_at"]),
    ("report_history", ["created_at", "updated_at"]),
    ("guardian_transfer_requests", ["created_at", "expires_at", "approved_at", "cancelled_at"]),
    ("guardian_alert_quota_usage", ["used_at"]),
    ("guardian_proxy_pay", ["created_at", "updated_at"]),
    ("emergency_call_sources", ["created_at", "updated_at"]),
    ("ai_call_reminders", ["created_at", "updated_at", "next_fire_at"]),
    ("reverse_guardian_invitations", ["created_at", "expires_at"]),
    ("health_metric_record", ["created_at", "measured_at"]),
    ("device_binding", ["bound_at", "last_sync_at", "token_expires_at"]),
    ("health_alerts", ["created_at", "updated_at", "last_occurred_at", "resolved_at"]),
    ("medical_records", ["created_at", "updated_at", "deleted_at"]),
    ("medical_record_files", ["created_at"]),
    ("brain_game_regions", ["synced_at"]),
    ("brain_game_scores", ["created_at"]),
    ("brain_game_challenges", ["created_at", "expires_at"]),
    ("brain_game_challenge_members", ["joined_at", "finished_at"]),
    ("device_catalog", ["created_at", "updated_at"]),
    ("device_user_bindings", ["created_at", "updated_at", "bound_at", "unbound_at"]),
    ("membership_plans", ["created_at", "updated_at"]),
    ("user_membership_subs", ["created_at", "updated_at", "start_at", "expire_at"]),
    ("free_member_quota", ["updated_at"]),
    ("asr_configs", ["updated_at"]),
]


def generate_sqls(dry_run: bool = True) -> List[str]:
    """生成所有 UPDATE SQL 语句。"""
    sqls = []
    for table, fields in TIME_FIELDS:
        for field in fields:
            sql = (
                f"UPDATE {table} SET {field} = DATE_ADD({field}, INTERVAL 8 HOUR) "
                f"WHERE {field} IS NOT NULL;"
            )
            sqls.append(sql)
    return sqls


async def run_migration(go: bool = False) -> None:
    """执行迁移。"""
    sqls = generate_sqls()
    print(f"共需迁移 {len(sqls)} 条 UPDATE 语句（涉及 {len(TIME_FIELDS)} 张表）")
    print("=" * 60)

    if not go:
        print(">>> DRY RUN 模式（仅打印 SQL，不执行）<<<")
        for i, sql in enumerate(sqls, 1):
            print(f"[{i:3d}] {sql}")
        print("=" * 60)
        print("如需实际执行，请加参数：python migration_timezone_bj_20260606.py --go")
        return

    # 实际执行
    print(">>> 开始执行迁移... <<<")
    try:
        import aiomysql
    except ImportError:
        print("错误：需要安装 aiomysql：pip install aiomysql")
        sys.exit(1)

    conn = await aiomysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        db=DB_NAME,
        charset="utf8mb4",
    )
    cursor = await conn.cursor()

    try:
        await conn.begin()
        for i, sql in enumerate(sqls, 1):
            try:
                await cursor.execute(sql)
                print(f"[{i:3d}/{len(sqls)}] OK: {sql[:80]}...")
            except Exception as e:
                print(f"[{i:3d}/{len(sqls)}] FAIL: {sql[:80]}... | 错误: {e}")
                await conn.rollback()
                print("\n>>> 迁移失败，已回滚所有变更 <<<")
                return
        await conn.commit()
        print("\n>>> 迁移成功完成！<<<")
    except Exception as e:
        await conn.rollback()
        print(f"\n>>> 迁移失败: {e} <<<")
        raise
    finally:
        await cursor.close()
        conn.close()


if __name__ == "__main__":
    go = "--go" in sys.argv
    asyncio.run(run_migration(go=go))
