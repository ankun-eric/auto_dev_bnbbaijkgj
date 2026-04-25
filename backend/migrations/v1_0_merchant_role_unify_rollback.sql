-- ============================================================
-- [PRD v1.0 §R1] 商家角色统一治理 — 回滚 SQL
-- 创建日期：2026-04-26
--
-- ⚠️ 适用场景：v1_0_merchant_role_unify.sql 执行后
--   线上发现回归 Bug 需要回退到迁移前的 role_code 文本值。
--
-- 回滚策略：
--   理论上 verifier→clerk、staff→clerk、owner→boss、manager→store_manager
--   是 N→1 收敛映射，无法 100% 通过 role_code 唯一反推。
--   因此本回滚脚本结合 member_role 物理枚举作为权威信号还原：
--     role_code='clerk' AND member_role='verifier' -> role_code='verifier'
--     role_code='clerk' AND member_role='staff'    -> role_code='staff'
--     role_code='boss'  AND member_role='owner'    -> role_code='owner'
--     role_code='store_manager' AND member_role='store_manager' -> role_code='manager'
--
-- 推荐做法（更安全）：
--   迁移前先做：
--     CREATE TABLE merchant_store_memberships_bk_20260426
--     AS SELECT * FROM merchant_store_memberships;
--   回滚时直接 UPDATE … FROM 备份表覆盖 role_code。
-- ============================================================

UPDATE merchant_store_memberships
   SET role_code='verifier'
 WHERE role_code='clerk' AND member_role='verifier';

UPDATE merchant_store_memberships
   SET role_code='staff'
 WHERE role_code='clerk' AND member_role='staff';

UPDATE merchant_store_memberships
   SET role_code='owner'
 WHERE role_code='boss' AND member_role='owner';

UPDATE merchant_store_memberships
   SET role_code='manager'
 WHERE role_code='store_manager' AND member_role='store_manager';
