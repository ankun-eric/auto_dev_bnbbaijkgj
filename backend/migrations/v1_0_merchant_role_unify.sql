-- ============================================================
-- [PRD v1.0 §R1] 商家角色统一治理 — 数据迁移（一次性）
-- 创建日期：2026-04-26
-- 作者：小白 AI
--
-- 治理目标：
--   merchant_store_memberships.role_code 字段（业务角色）
--   仅保留 4 个值：boss / store_manager / finance / clerk
--
-- 注意：
--   1) 物理 ENUM merchant_store_memberships.member_role 仍保留 5 值
--      （owner/staff/store_manager/verifier/finance），不在本脚本中变更，
--      避免破坏存量数据。业务上一律以 role_code 为权威。
--   2) 本脚本与 backend/app/main.py:_migrate_merchant_role_unify_v1
--      逻辑一致，启动时已自动执行。本 SQL 主要作为 DBA 手动操作
--      与回滚备份的依据。
--   3) 执行前请务必 mysqldump 备份 merchant_store_memberships 表。
--
-- 兼容映射表：
--    verifier -> clerk
--    staff    -> clerk
--    owner    -> boss        (仅 role_code 文本，物理 enum 不动)
--    manager  -> store_manager
-- ============================================================

-- 1) 历史别名 → 4 角色之一
UPDATE merchant_store_memberships SET role_code='clerk'
  WHERE role_code='verifier';

UPDATE merchant_store_memberships SET role_code='clerk'
  WHERE role_code='staff';

UPDATE merchant_store_memberships SET role_code='boss'
  WHERE role_code='owner';

UPDATE merchant_store_memberships SET role_code='store_manager'
  WHERE role_code='manager';

-- 2) role_code 为空时按 member_role 物理枚举回填
UPDATE merchant_store_memberships
   SET role_code='boss'
 WHERE (role_code IS NULL OR role_code='')
   AND member_role='owner';

UPDATE merchant_store_memberships
   SET role_code='store_manager'
 WHERE (role_code IS NULL OR role_code='')
   AND member_role='store_manager';

UPDATE merchant_store_memberships
   SET role_code='finance'
 WHERE (role_code IS NULL OR role_code='')
   AND member_role='finance';

UPDATE merchant_store_memberships
   SET role_code='clerk'
 WHERE (role_code IS NULL OR role_code='')
   AND member_role='verifier';

UPDATE merchant_store_memberships
   SET role_code='clerk'
 WHERE (role_code IS NULL OR role_code='')
   AND member_role='staff';

-- 3) 校验：迁移后应仅剩 4 角色
--    如果以下 SELECT 返回 0 行，则迁移完成且无脏数据。
--    SELECT role_code, COUNT(*) FROM merchant_store_memberships
--     WHERE role_code NOT IN ('boss','store_manager','finance','clerk')
--     GROUP BY role_code;
