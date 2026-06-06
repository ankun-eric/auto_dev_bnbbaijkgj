-- ============================================================
-- 日期时区简化优化方案：数据库迁移 SQL 脚本
-- 目标：所有时间字段从 UTC 统一加 8 小时转为北京时间
-- 生成日期：2026-06-06
-- 注意：此脚本应仅在低峰期执行，建议先备份数据库
-- ============================================================

-- ────────────── 用户体系 ──────────────
UPDATE users SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE users SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE users SET last_login_at = DATE_ADD(last_login_at, INTERVAL 8 HOUR) WHERE last_login_at IS NOT NULL;
UPDATE users SET deleted_at = DATE_ADD(deleted_at, INTERVAL 8 HOUR) WHERE deleted_at IS NOT NULL;

UPDATE relation_types SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE relation_types SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE family_members SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE family_members SET status_changed_at = DATE_ADD(status_changed_at, INTERVAL 8 HOUR) WHERE status_changed_at IS NOT NULL;

UPDATE verification_codes SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE verification_codes SET expires_at = DATE_ADD(expires_at, INTERVAL 8 HOUR) WHERE expires_at IS NOT NULL;

UPDATE account_identities SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE account_identities SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 商家体系 ──────────────
UPDATE merchant_profiles SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE merchant_profiles SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE merchant_stores SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE merchant_stores SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE merchant_store_memberships SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE merchant_store_memberships SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE merchant_store_permissions SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE merchant_notifications SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE merchant_order_verifications SET verified_at = DATE_ADD(verified_at, INTERVAL 8 HOUR) WHERE verified_at IS NOT NULL;

UPDATE merchant_categories SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE merchant_categories SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE merchant_role_templates SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE merchant_role_templates SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE order_attachments SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE order_attachments SET deleted_at = DATE_ADD(deleted_at, INTERVAL 8 HOUR) WHERE deleted_at IS NOT NULL;

UPDATE merchant_business_hours SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE merchant_business_hours SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE merchant_invoice_profiles SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE merchant_invoice_profiles SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE settlement_statements SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE settlement_statements SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE settlement_statements SET confirmed_at = DATE_ADD(confirmed_at, INTERVAL 8 HOUR) WHERE confirmed_at IS NOT NULL;
UPDATE settlement_statements SET settled_at = DATE_ADD(settled_at, INTERVAL 8 HOUR) WHERE settled_at IS NOT NULL;

UPDATE settlement_payment_proofs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE settlement_payment_proofs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE settlement_payment_proofs SET paid_at = DATE_ADD(paid_at, INTERVAL 8 HOUR) WHERE paid_at IS NOT NULL;

UPDATE merchant_export_tasks SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE merchant_export_tasks SET finished_at = DATE_ADD(finished_at, INTERVAL 8 HOUR) WHERE finished_at IS NOT NULL;

-- ────────────── 健康档案 ──────────────
UPDATE health_profiles SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE health_profiles SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE disease_presets SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE disease_presets SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE allergy_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE medical_histories SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE family_medical_histories SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE medication_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE visit_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE checkup_reports SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE checkup_reports SET share_expires_at = DATE_ADD(share_expires_at, INTERVAL 8 HOUR) WHERE share_expires_at IS NOT NULL;

UPDATE checkup_indicators SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE report_alerts SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── AI 对话 ──────────────
UPDATE chat_sessions SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE chat_sessions SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE chat_sessions SET last_active_at = DATE_ADD(last_active_at, INTERVAL 8 HOUR) WHERE last_active_at IS NOT NULL;
UPDATE chat_sessions SET archived_at = DATE_ADD(archived_at, INTERVAL 8 HOUR) WHERE archived_at IS NOT NULL;
UPDATE chat_sessions SET pinned_at = DATE_ADD(pinned_at, INTERVAL 8 HOUR) WHERE pinned_at IS NOT NULL;

UPDATE chat_messages SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 中医 ──────────────
UPDATE tcm_configs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE tcm_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE tcm_diagnoses SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE constitution_answers SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE constitution_content_configs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE constitution_content_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 服务与订单 ──────────────
UPDATE service_categories SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE service_items SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE service_items SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE orders SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE orders SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE orders SET verified_at = DATE_ADD(verified_at, INTERVAL 8 HOUR) WHERE verified_at IS NOT NULL;

UPDATE order_reviews SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 专家/预约 ──────────────
UPDATE experts SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE expert_schedules SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE appointments SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 积分与会员 ──────────────
UPDATE points_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE member_levels SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE sign_in_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE points_mall_items SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE points_mall_goods_change_log SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE points_exchanges SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE point_exchange_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE point_exchange_records SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE point_exchange_records SET exchange_time = DATE_ADD(exchange_time, INTERVAL 8 HOUR) WHERE exchange_time IS NOT NULL;
UPDATE point_exchange_records SET expire_at = DATE_ADD(expire_at, INTERVAL 8 HOUR) WHERE expire_at IS NOT NULL;
UPDATE point_exchange_records SET used_at = DATE_ADD(used_at, INTERVAL 8 HOUR) WHERE used_at IS NOT NULL;

-- ────────────── 健康计划 ──────────────
UPDATE health_plans SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE health_tasks SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE task_check_ins SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 健康知识 ──────────────
UPDATE articles SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE articles SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE article_categories SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE news SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE news SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE news_tag_history SET last_used_at = DATE_ADD(last_used_at, INTERVAL 8 HOUR) WHERE last_used_at IS NOT NULL;

UPDATE comments SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE favorites SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 消息通知 ──────────────
UPDATE notifications SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE notifications SET read_at = DATE_ADD(read_at, INTERVAL 8 HOUR) WHERE read_at IS NOT NULL;

-- ────────────── 系统配置 ──────────────
UPDATE system_configs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE system_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 支付配置 ──────────────
UPDATE payment_channels SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE payment_channels SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE payment_channels SET last_test_at = DATE_ADD(last_test_at, INTERVAL 8 HOUR) WHERE last_test_at IS NOT NULL;

UPDATE ai_model_templates SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE ai_model_templates SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE ai_model_configs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE ai_model_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE ai_model_configs SET template_synced_at = DATE_ADD(template_synced_at, INTERVAL 8 HOUR) WHERE template_synced_at IS NOT NULL;
UPDATE ai_model_configs SET last_test_time = DATE_ADD(last_test_time, INTERVAL 8 HOUR) WHERE last_test_time IS NOT NULL;

-- ────────────── 短信 / 邮件 ──────────────
UPDATE sms_configs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE sms_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE sms_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE sms_templates SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE sms_templates SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE email_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 客服 ──────────────
UPDATE customer_service_sessions SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE customer_service_sessions SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE customer_service_messages SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 知识库 ──────────────
UPDATE knowledge_bases SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE knowledge_bases SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE knowledge_entries SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE knowledge_entries SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE knowledge_entries SET last_hit_at = DATE_ADD(last_hit_at, INTERVAL 8 HOUR) WHERE last_hit_at IS NOT NULL;

UPDATE knowledge_entry_products SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE knowledge_search_configs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE knowledge_search_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE knowledge_fallback_configs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE knowledge_fallback_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE knowledge_scene_bindings SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE knowledge_hit_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE knowledge_missed_questions SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE knowledge_missed_questions SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE knowledge_import_tasks SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE knowledge_import_tasks SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── AI 中心配置 ──────────────
UPDATE ai_sensitive_words SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE ai_sensitive_words SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE ai_prompt_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE ai_disclaimer_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── COS 对象存储 ──────────────
UPDATE cos_configs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE cos_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE cos_files SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── COS 迁移 ──────────────
UPDATE cos_migration_tasks SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE cos_migration_tasks SET started_at = DATE_ADD(started_at, INTERVAL 8 HOUR) WHERE started_at IS NOT NULL;
UPDATE cos_migration_tasks SET completed_at = DATE_ADD(completed_at, INTERVAL 8 HOUR) WHERE completed_at IS NOT NULL;

UPDATE cos_migration_details SET migrated_at = DATE_ADD(migrated_at, INTERVAL 8 HOUR) WHERE migrated_at IS NOT NULL;

-- ────────────── OCR ──────────────
UPDATE ocr_configs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE ocr_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE ocr_provider_configs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE ocr_provider_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE ocr_scene_templates SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE ocr_scene_templates SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE ocr_call_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE checkup_report_details SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE drug_identify_details SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 聊天分享 ──────────────
UPDATE chat_share_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── Prompt 模板 ──────────────
UPDATE prompt_templates SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE prompt_templates SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE prompt_type_config SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE prompt_type_config SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 分享链接 ──────────────
UPDATE share_links SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 首页配置 ──────────────
UPDATE home_menu_items SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE home_menu_items SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE home_banners SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE home_banners SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 搜索 ──────────────
UPDATE search_histories SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE search_histories SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE search_hot_words SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE search_hot_words SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE search_recommend_words SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE search_recommend_words SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE search_block_words SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE search_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 首页公告 ──────────────
UPDATE home_notices SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE home_notices SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE home_notices SET start_time = DATE_ADD(start_time, INTERVAL 8 HOUR) WHERE start_time IS NOT NULL;
UPDATE home_notices SET end_time = DATE_ADD(end_time, INTERVAL 8 HOUR) WHERE end_time IS NOT NULL;

-- ────────────── 底部导航 ──────────────
UPDATE bottom_nav_config SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE bottom_nav_config SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 用药提醒 ──────────────
UPDATE medication_reminders SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE medication_check_ins SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE medication_check_ins SET check_in_time = DATE_ADD(check_in_time, INTERVAL 8 HOUR) WHERE check_in_time IS NOT NULL;

-- ────────────── 健康打卡计划 ──────────────
UPDATE health_checkin_items SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE health_checkin_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE health_checkin_records SET check_in_time = DATE_ADD(check_in_time, INTERVAL 8 HOUR) WHERE check_in_time IS NOT NULL;

UPDATE plan_template_categories SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE recommended_plans SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE recommended_plan_tasks SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE user_plans SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE user_plan_tasks SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE user_plan_task_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE user_plan_task_records SET check_in_time = DATE_ADD(check_in_time, INTERVAL 8 HOUR) WHERE check_in_time IS NOT NULL;

UPDATE notification_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 城市 ──────────────
UPDATE cities SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE cities SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 功能按钮 ──────────────
UPDATE chat_function_buttons SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE chat_function_buttons SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 问卷体系 ──────────────
UPDATE questionnaire_template SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE questionnaire_template SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE questionnaire_question SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE questionnaire_question SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE questionnaire_classification_rule SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE questionnaire_classification_rule SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE questionnaire_recommendation SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE questionnaire_recommendation SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE questionnaire_answer SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE questionnaire_answer SET completed_at = DATE_ADD(completed_at, INTERVAL 8 HOUR) WHERE completed_at IS NOT NULL;
UPDATE questionnaire_answer SET ai_generated_at = DATE_ADD(ai_generated_at, INTERVAL 8 HOUR) WHERE ai_generated_at IS NOT NULL;

-- ────────────── 标签体系 ──────────────
UPDATE tags SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE tags SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE goods_tags SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE questionnaire_recommend_config SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE questionnaire_recommend_config SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 健康自查 ──────────────
UPDATE body_part_dict SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE body_part_dict SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE health_check_template SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE health_check_template SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 数字人 ──────────────
UPDATE digital_humans SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE digital_humans SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE voice_call_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE voice_call_records SET start_time = DATE_ADD(start_time, INTERVAL 8 HOUR) WHERE start_time IS NOT NULL;
UPDATE voice_call_records SET end_time = DATE_ADD(end_time, INTERVAL 8 HOUR) WHERE end_time IS NOT NULL;

UPDATE voice_service_configs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE voice_service_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 家庭健康档案共管 ──────────────
UPDATE family_management SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE family_management SET cancelled_at = DATE_ADD(cancelled_at, INTERVAL 8 HOUR) WHERE cancelled_at IS NOT NULL;

UPDATE family_invitations SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE family_invitations SET expires_at = DATE_ADD(expires_at, INTERVAL 8 HOUR) WHERE expires_at IS NOT NULL;
UPDATE family_invitations SET accepted_at = DATE_ADD(accepted_at, INTERVAL 8 HOUR) WHERE accepted_at IS NOT NULL;

UPDATE management_operation_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 系统消息 ──────────────
UPDATE system_messages SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE system_messages SET read_at = DATE_ADD(read_at, INTERVAL 8 HOUR) WHERE read_at IS NOT NULL;

-- ────────────── 商品体系 ──────────────
UPDATE product_categories SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE product_categories SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE appointment_forms SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE appointment_forms SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE appointment_form_fields SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE appointment_form_fields SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE products SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE products SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE product_skus SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE product_skus SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE product_stores SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 收货地址 ──────────────
UPDATE user_addresses SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE user_addresses SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 优惠券 ──────────────
UPDATE coupons SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE coupons SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE coupons SET valid_start = DATE_ADD(valid_start, INTERVAL 8 HOUR) WHERE valid_start IS NOT NULL;
UPDATE coupons SET valid_end = DATE_ADD(valid_end, INTERVAL 8 HOUR) WHERE valid_end IS NOT NULL;
UPDATE coupons SET offline_at = DATE_ADD(offline_at, INTERVAL 8 HOUR) WHERE offline_at IS NOT NULL;

UPDATE user_coupons SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE user_coupons SET used_at = DATE_ADD(used_at, INTERVAL 8 HOUR) WHERE used_at IS NOT NULL;
UPDATE user_coupons SET expire_at = DATE_ADD(expire_at, INTERVAL 8 HOUR) WHERE expire_at IS NOT NULL;

UPDATE coupon_grants SET granted_at = DATE_ADD(granted_at, INTERVAL 8 HOUR) WHERE granted_at IS NOT NULL;
UPDATE coupon_grants SET used_at = DATE_ADD(used_at, INTERVAL 8 HOUR) WHERE used_at IS NOT NULL;

UPDATE coupon_code_batches SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE coupon_code_batches SET expire_at = DATE_ADD(expire_at, INTERVAL 8 HOUR) WHERE expire_at IS NOT NULL;
UPDATE coupon_code_batches SET voided_at = DATE_ADD(voided_at, INTERVAL 8 HOUR) WHERE voided_at IS NOT NULL;

UPDATE coupon_redeem_codes SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE coupon_redeem_codes SET sold_at = DATE_ADD(sold_at, INTERVAL 8 HOUR) WHERE sold_at IS NOT NULL;
UPDATE coupon_redeem_codes SET used_at = DATE_ADD(used_at, INTERVAL 8 HOUR) WHERE used_at IS NOT NULL;
UPDATE coupon_redeem_codes SET voided_at = DATE_ADD(voided_at, INTERVAL 8 HOUR) WHERE voided_at IS NOT NULL;

UPDATE coupon_op_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE partners SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE partners SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 审核 ──────────────
UPDATE audit_phones SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE audit_phones SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE audit_requests SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE audit_requests SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE audit_requests SET approved_at = DATE_ADD(approved_at, INTERVAL 8 HOUR) WHERE approved_at IS NOT NULL;

UPDATE audit_codes SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE audit_codes SET expires_at = DATE_ADD(expires_at, INTERVAL 8 HOUR) WHERE expires_at IS NOT NULL;

UPDATE audit_lockouts SET last_fail_at = DATE_ADD(last_fail_at, INTERVAL 8 HOUR) WHERE last_fail_at IS NOT NULL;

-- ────────────── 统一订单 ──────────────
UPDATE unified_orders SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE unified_orders SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE unified_orders SET paid_at = DATE_ADD(paid_at, INTERVAL 8 HOUR) WHERE paid_at IS NOT NULL;
UPDATE unified_orders SET shipped_at = DATE_ADD(shipped_at, INTERVAL 8 HOUR) WHERE shipped_at IS NOT NULL;
UPDATE unified_orders SET received_at = DATE_ADD(received_at, INTERVAL 8 HOUR) WHERE received_at IS NOT NULL;
UPDATE unified_orders SET completed_at = DATE_ADD(completed_at, INTERVAL 8 HOUR) WHERE completed_at IS NOT NULL;
UPDATE unified_orders SET cancelled_at = DATE_ADD(cancelled_at, INTERVAL 8 HOUR) WHERE cancelled_at IS NOT NULL;
UPDATE unified_orders SET store_confirmed_at = DATE_ADD(store_confirmed_at, INTERVAL 8 HOUR) WHERE store_confirmed_at IS NOT NULL;

UPDATE order_items SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE order_items SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE order_items SET appointment_time = DATE_ADD(appointment_time, INTERVAL 8 HOUR) WHERE appointment_time IS NOT NULL;

UPDATE order_redemptions SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE order_redemptions SET redeemed_at = DATE_ADD(redeemed_at, INTERVAL 8 HOUR) WHERE redeemed_at IS NOT NULL;

-- ────────────── 会员码/签到 ──────────────
UPDATE member_qr_tokens SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE member_qr_tokens SET expires_at = DATE_ADD(expires_at, INTERVAL 8 HOUR) WHERE expires_at IS NOT NULL;

UPDATE checkin_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE checkin_records SET checked_in_at = DATE_ADD(checked_in_at, INTERVAL 8 HOUR) WHERE checked_in_at IS NOT NULL;

UPDATE store_visit_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE store_visit_records SET visited_at = DATE_ADD(visited_at, INTERVAL 8 HOUR) WHERE visited_at IS NOT NULL;

-- ────────────── 退款 ──────────────
UPDATE refund_requests SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE refund_requests SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 微信绑定/订单笔记/预约日志 ──────────────
UPDATE staff_wechat_bindings SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE staff_wechat_bindings SET bound_at = DATE_ADD(bound_at, INTERVAL 8 HOUR) WHERE bound_at IS NOT NULL;

UPDATE order_notes SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE order_appointment_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 地图配置 ──────────────
UPDATE map_config SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE map_config SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE map_test_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 卡功能 ──────────────
UPDATE card_definitions SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE card_definitions SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE card_items SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE user_cards SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE user_cards SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE user_cards SET valid_from = DATE_ADD(valid_from, INTERVAL 8 HOUR) WHERE valid_from IS NOT NULL;
UPDATE user_cards SET valid_to = DATE_ADD(valid_to, INTERVAL 8 HOUR) WHERE valid_to IS NOT NULL;

UPDATE card_usage_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE card_usage_logs SET used_at = DATE_ADD(used_at, INTERVAL 8 HOUR) WHERE used_at IS NOT NULL;

UPDATE card_redemption_codes SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE card_redemption_codes SET issued_at = DATE_ADD(issued_at, INTERVAL 8 HOUR) WHERE issued_at IS NOT NULL;
UPDATE card_redemption_codes SET expires_at = DATE_ADD(expires_at, INTERVAL 8 HOUR) WHERE expires_at IS NOT NULL;
UPDATE card_redemption_codes SET used_at = DATE_ADD(used_at, INTERVAL 8 HOUR) WHERE used_at IS NOT NULL;

-- ────────────── 商家日历/预约通知日志 ──────────────
UPDATE merchant_calendar_views SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE merchant_calendar_views SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE booking_notification_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── AI 首页配置日志 ──────────────
UPDATE ai_home_config_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 用药计划 ──────────────
UPDATE medication_plans SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE medication_plans SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE medication_logs SET checked_at = DATE_ADD(checked_at, INTERVAL 8 HOUR) WHERE checked_at IS NOT NULL;

-- ────────────── 药品库 ──────────────
UPDATE medication_library SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE medication_library SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE medication_library_pending SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE medication_library_pending SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE medication_library_pending SET last_hit_at = DATE_ADD(last_hit_at, INTERVAL 8 HOUR) WHERE last_hit_at IS NOT NULL;
UPDATE medication_library_pending SET operated_at = DATE_ADD(operated_at, INTERVAL 8 HOUR) WHERE operated_at IS NOT NULL;

-- ────────────── 健康信息扩展 / 健康事件 ──────────────
UPDATE health_info_extra SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE health_info_extra SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE health_events SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE health_events SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 设备场景 / 绑定 ──────────────
UPDATE device_scene_group SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE device_scene_group SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE device_bindings SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE device_bindings SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE device_bindings SET bound_at = DATE_ADD(bound_at, INTERVAL 8 HOUR) WHERE bound_at IS NOT NULL;
UPDATE device_bindings SET last_sync_at = DATE_ADD(last_sync_at, INTERVAL 8 HOUR) WHERE last_sync_at IS NOT NULL;

-- ────────────── 提醒设置 / AI 外呼 ──────────────
UPDATE reminder_settings SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE reminder_settings SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE guardian_ai_call_settings SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE guardian_ai_call_settings SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE medical_record_cards SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE medical_record_cards SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── AI 外呼会员等级/全局配置/用户会员/呼叫日志 ──────────────
UPDATE ai_call_membership_levels SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE ai_call_membership_levels SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE ai_call_global_config SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE ai_call_global_config SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE user_memberships SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE user_memberships SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE ai_call_logs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE ai_call_logs SET call_at = DATE_ADD(call_at, INTERVAL 8 HOUR) WHERE call_at IS NOT NULL;

-- ────────────── 异常阈值/告警模板/告警日志 ──────────────
UPDATE abnormal_thresholds SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE abnormal_thresholds SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE alert_message_templates SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE alert_message_templates SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE family_alert_logs SET pushed_at = DATE_ADD(pushed_at, INTERVAL 8 HOUR) WHERE pushed_at IS NOT NULL;
UPDATE family_alert_logs SET clicked_at = DATE_ADD(clicked_at, INTERVAL 8 HOUR) WHERE clicked_at IS NOT NULL;

-- ────────────── 虚拟档案迁移 ──────────────
UPDATE virtual_member_migrations SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE virtual_member_migrations SET confirmed_at = DATE_ADD(confirmed_at, INTERVAL 8 HOUR) WHERE confirmed_at IS NOT NULL;

-- ────────────── 健康提醒 / 告警通知 ──────────────
UPDATE health_reminders SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE health_reminders SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE health_reminders SET completed_at = DATE_ADD(completed_at, INTERVAL 8 HOUR) WHERE completed_at IS NOT NULL;

UPDATE health_alert_notifications SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE health_alert_notifications SET sent_at = DATE_ADD(sent_at, INTERVAL 8 HOUR) WHERE sent_at IS NOT NULL;

-- ────────────── 报告历史 ──────────────
UPDATE report_history SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE report_history SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 守护人转移 / 告警额度 / 代付 / 紧急呼叫 / AI 外呼提醒 ──────────────
UPDATE guardian_transfer_requests SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE guardian_transfer_requests SET expires_at = DATE_ADD(expires_at, INTERVAL 8 HOUR) WHERE expires_at IS NOT NULL;
UPDATE guardian_transfer_requests SET approved_at = DATE_ADD(approved_at, INTERVAL 8 HOUR) WHERE approved_at IS NOT NULL;
UPDATE guardian_transfer_requests SET cancelled_at = DATE_ADD(cancelled_at, INTERVAL 8 HOUR) WHERE cancelled_at IS NOT NULL;

UPDATE guardian_alert_quota_usage SET used_at = DATE_ADD(used_at, INTERVAL 8 HOUR) WHERE used_at IS NOT NULL;

UPDATE guardian_proxy_pay SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE guardian_proxy_pay SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE emergency_call_sources SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE emergency_call_sources SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE ai_call_reminders SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE ai_call_reminders SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE ai_call_reminders SET next_fire_at = DATE_ADD(next_fire_at, INTERVAL 8 HOUR) WHERE next_fire_at IS NOT NULL;

-- ────────────── 反向守护邀请 ──────────────
UPDATE reverse_guardian_invitations SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE reverse_guardian_invitations SET expires_at = DATE_ADD(expires_at, INTERVAL 8 HOUR) WHERE expires_at IS NOT NULL;

-- ────────────── 健康档案 V3 (health_v3.py) ──────────────
UPDATE health_metric_record SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE health_metric_record SET measured_at = DATE_ADD(measured_at, INTERVAL 8 HOUR) WHERE measured_at IS NOT NULL;

UPDATE device_binding SET bound_at = DATE_ADD(bound_at, INTERVAL 8 HOUR) WHERE bound_at IS NOT NULL;
UPDATE device_binding SET last_sync_at = DATE_ADD(last_sync_at, INTERVAL 8 HOUR) WHERE last_sync_at IS NOT NULL;
UPDATE device_binding SET token_expires_at = DATE_ADD(token_expires_at, INTERVAL 8 HOUR) WHERE token_expires_at IS NOT NULL;

-- ────────────── 健康档案 V5 (health_archive_v5.py) ──────────────
UPDATE health_alerts SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE health_alerts SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE health_alerts SET last_occurred_at = DATE_ADD(last_occurred_at, INTERVAL 8 HOUR) WHERE last_occurred_at IS NOT NULL;
UPDATE health_alerts SET resolved_at = DATE_ADD(resolved_at, INTERVAL 8 HOUR) WHERE resolved_at IS NOT NULL;

UPDATE medical_records SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE medical_records SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE medical_records SET deleted_at = DATE_ADD(deleted_at, INTERVAL 8 HOUR) WHERE deleted_at IS NOT NULL;

UPDATE medical_record_files SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

-- ────────────── 益智乐园 (brain_game_models.py) ──────────────
UPDATE brain_game_regions SET synced_at = DATE_ADD(synced_at, INTERVAL 8 HOUR) WHERE synced_at IS NOT NULL;

UPDATE brain_game_scores SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;

UPDATE brain_game_challenges SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE brain_game_challenges SET expires_at = DATE_ADD(expires_at, INTERVAL 8 HOUR) WHERE expires_at IS NOT NULL;

UPDATE brain_game_challenge_members SET joined_at = DATE_ADD(joined_at, INTERVAL 8 HOUR) WHERE joined_at IS NOT NULL;
UPDATE brain_game_challenge_members SET finished_at = DATE_ADD(finished_at, INTERVAL 8 HOUR) WHERE finished_at IS NOT NULL;

-- ────────────── 设备 V2 (devices_v2.py) ──────────────
UPDATE device_catalog SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE device_catalog SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE device_user_bindings SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE device_user_bindings SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE device_user_bindings SET bound_at = DATE_ADD(bound_at, INTERVAL 8 HOUR) WHERE bound_at IS NOT NULL;
UPDATE device_user_bindings SET unbound_at = DATE_ADD(unbound_at, INTERVAL 8 HOUR) WHERE unbound_at IS NOT NULL;

-- ────────────── 会员套餐 (membership_plan.py) ──────────────
UPDATE membership_plans SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE membership_plans SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

UPDATE user_membership_subs SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE user_membership_subs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;
UPDATE user_membership_subs SET start_at = DATE_ADD(start_at, INTERVAL 8 HOUR) WHERE start_at IS NOT NULL;
UPDATE user_membership_subs SET expire_at = DATE_ADD(expire_at, INTERVAL 8 HOUR) WHERE expire_at IS NOT NULL;

UPDATE free_member_quota SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── ASR 配置 ──────────────
UPDATE asr_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── OCR 上传统计 ──────────────
UPDATE ocr_upload_configs SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 应用设置 ──────────────
UPDATE app_settings SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 视频客服配置 ──────────────
UPDATE video_consult_config SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE video_consult_config SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 用户反馈 ──────────────
UPDATE user_feedback SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE user_feedback SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ────────────── 用户健康画像 ──────────────
UPDATE user_health_profiles SET created_at = DATE_ADD(created_at, INTERVAL 8 HOUR) WHERE created_at IS NOT NULL;
UPDATE user_health_profiles SET updated_at = DATE_ADD(updated_at, INTERVAL 8 HOUR) WHERE updated_at IS NOT NULL;

-- ============================================================
-- 迁移完成
-- ============================================================
