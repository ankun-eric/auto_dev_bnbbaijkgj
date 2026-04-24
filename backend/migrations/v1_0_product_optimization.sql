-- 商品功能优化 v1.0 迁移脚本
-- 对应 PRD：商品功能优化需求 PRD v1.0（2026-04-24）
--
-- 变更内容：
-- 1) 彻底删除 products 表的 valid_start_date / valid_end_date 字段（用户决策 Q11 = C）
-- 2) 新增 products.marketing_badges JSON 字段，存储运营勾选的营销角标
--    允许取值：'limited' / 'hot' / 'new' / 'recommend'
--    前端按 limited > hot > new > recommend 的优先级只渲染 1 个
--
-- ⚠️ 资深技术经理风险提示：DROP COLUMN 属于不可逆变更。
-- 执行前必须先做一次数据库完整备份或至少导出 products 表快照（保留至少 30 天）。
--
-- 建议备份命令（在服务器上执行）：
--   mysqldump -u<user> -p<pass> <database> products > products_backup_v1_0.sql
--
-- 本项目在后端启动时会自动通过 app/services/schema_sync.py 幂等地执行等价逻辑，
-- 该文件仅作为手动运维脚本与审计留痕。

-- Step 1: 新增 marketing_badges 列
ALTER TABLE products ADD COLUMN IF NOT EXISTS marketing_badges JSON NULL;

-- Step 2: 删除 valid_start_date / valid_end_date 列（彻底清空）
-- 注：部分 MySQL 版本不支持 IF EXISTS，可去掉 IF EXISTS；也可在应用层 schema_sync 中处理
ALTER TABLE products DROP COLUMN valid_start_date;
ALTER TABLE products DROP COLUMN valid_end_date;
