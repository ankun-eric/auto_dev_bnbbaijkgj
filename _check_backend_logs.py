import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

i, o, e = ssh.exec_command(
    "docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --tail 200 2>&1 | grep -E 'tag_recommend|symptom|tag_columns|constitution_tags|drop|ALTER' | tail -40",
    timeout=30,
)
print(o.read().decode("utf-8", "replace"))
print("ERR:", e.read().decode("utf-8", "replace"))

# 也查看是否文件已正确部署
i2, o2, e2 = ssh.exec_command(
    "grep -E 'tag_columns_added|_drop_symptom_tags_column|is_locked' /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/backend/app/services/prd_tag_recommend_v1_migration.py | head -20",
    timeout=30,
)
print("DEPLOYED FILE GREP:")
print(o2.read().decode("utf-8", "replace"))

ssh.close()
