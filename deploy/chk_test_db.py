import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=15)

sql = """
SELECT 'merchant_stores' as tbl, COUNT(*) as cnt FROM merchant_stores
UNION ALL SELECT 'merchant_profiles', COUNT(*) FROM merchant_profiles
UNION ALL SELECT 'merchant_store_memberships', COUNT(*) FROM merchant_store_memberships
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'staff_wechat_bindings', COUNT(*) FROM staff_wechat_bindings
UNION ALL SELECT 'merchant_categories', COUNT(*) FROM merchant_categories;
"""

cmd = f"""docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 bini_health -e "{sql}" 2>/dev/null"""
si, so, se = c.exec_command(cmd, timeout=15)
print(so.read().decode('utf-8').strip())
c.close()
