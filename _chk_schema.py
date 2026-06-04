import paramiko
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

def mysql(sql):
    cmd = f"docker exec {PROJECT_ID}-db mysql -uroot -pbini_health_2026 -t -e \"{sql}\" bini_health 2>/dev/null"
    _, out, _ = cli.exec_command(cmd, timeout=60)
    return out.read().decode("utf-8", errors="replace")

print("=== family_invitations 列 ===")
print(mysql("DESC family_invitations;"))

print("=== family_management 列 ===")
print(mysql("DESC family_management;"))

print("=== health_info_extra 列 ===")
print(mysql("DESC health_info_extra;"))

print("=== 引用 family_members 的所有外键 ===")
print(mysql("SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA='bini_health' AND REFERENCED_TABLE_NAME='family_members';"))

print("=== 引用 health_profiles 的所有外键 ===")
print(mysql("SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA='bini_health' AND REFERENCED_TABLE_NAME='health_profiles';"))

print("=== 查询脏数据下挂的具体记录数 ===")
print(mysql("SELECT COUNT(*) AS health_profiles_cnt FROM health_profiles WHERE family_member_id IN (141,142,143,144,145,146,147,148,149,150,151,152,153,154,162,197);"))
print(mysql("SELECT COUNT(*) AS family_invitations_cnt FROM family_invitations WHERE member_id IN (141,142,143,144,145,146,147,148,149,150,151,152,153,154,162,197);"))
print(mysql("SELECT COUNT(*) AS family_management_cnt FROM family_management WHERE managed_member_id IN (141,142,143,144,145,146,147,148,149,150,151,152,153,154,162,197);"))
print(mysql("SELECT COUNT(*) AS health_info_extra_cnt FROM health_info_extra WHERE profile_id IN (SELECT id FROM health_profiles WHERE family_member_id IN (141,142,143,144,145,146,147,148,149,150,151,152,153,154,162,197));"))

cli.close()
