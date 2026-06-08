-- ============================================================
-- 迁移脚本：健康档案防重复 - Step 7: NULL → 0 + 字段定义 + 唯一索引
-- 版本: v1.0
-- 日期: 2026-06-08
-- 描述: 将 family_member_id 从 NULL 改为 0，添加 NOT NULL 约束，
--       然后创建 (user_id, family_member_id) 联合唯一索引。
-- 前提: Step 1 脏数据清理必须已完成。
-- ============================================================

-- 1. 临时关闭外键检查（因为 family_member_id=0 不指向真实 FamilyMember）
SET FOREIGN_KEY_CHECKS = 0;

-- 2. 将现存本人档案的 family_member_id 从 NULL 改为 0
UPDATE health_profiles SET family_member_id = 0 WHERE family_member_id IS NULL;

-- 3. 修改字段定义：BIGINT NOT NULL DEFAULT 0
ALTER TABLE health_profiles 
  MODIFY COLUMN family_member_id BIGINT NOT NULL DEFAULT 0;

-- 4. 添加联合唯一索引
ALTER TABLE health_profiles 
  ADD UNIQUE INDEX idx_user_family_member (user_id, family_member_id);

-- 5. 恢复外键检查
SET FOREIGN_KEY_CHECKS = 1;
