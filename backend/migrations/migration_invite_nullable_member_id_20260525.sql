-- [BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 允许情况 2 的邀请记录 member_id 为 NULL
ALTER TABLE family_invitations MODIFY COLUMN member_id INT NULL;
