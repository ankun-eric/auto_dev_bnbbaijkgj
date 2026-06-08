-- ============================================================
-- 迁移脚本：健康档案防重复 - Step 1: 脏数据清理
-- 版本: v1.0
-- 日期: 2026-06-08
-- 描述: 保留每个用户最早创建的本人档案（family_member_id IS NULL），
--       删除多余的重复记录。
-- ============================================================

-- 1. 查询脏数据（审核用，可在执行前手动检查）
SELECT user_id, COUNT(*) AS cnt
FROM health_profiles
WHERE family_member_id IS NULL
GROUP BY user_id
HAVING COUNT(*) > 1;

-- 2. 保留最早创建的（MIN(id)），删除多余的
DELETE hp FROM health_profiles hp
INNER JOIN (
    SELECT user_id, MIN(id) AS keep_id
    FROM health_profiles
    WHERE family_member_id IS NULL
    GROUP BY user_id
    HAVING COUNT(*) > 1
) keeper ON hp.user_id = keeper.user_id
WHERE hp.family_member_id IS NULL
  AND hp.id != keeper.keep_id;

-- 3. 执行后验证（期望返回 Empty set）
SELECT user_id, COUNT(*) AS cnt
FROM health_profiles
WHERE family_member_id IS NULL
GROUP BY user_id
HAVING COUNT(*) > 1;
