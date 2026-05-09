# -*- coding: utf-8 -*-
"""复查 sid=215 的所有 chat_messages，确认 user + AI 都入库且 parent_id 关联正确。"""
import paramiko, sys, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
sql = (
    "SELECT id, session_id, role, source, parent_id, LEFT(CONVERT(content USING utf8mb4), 60) AS content "
    "FROM bini_health.chat_messages WHERE session_id IN (215, 216) ORDER BY id;"
)
cmd = f"docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 --default-character-set=utf8mb4 -B -e \"{sql}\" 2>&1"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
out = stdout.read().decode("utf-8", errors="replace")
print(out)
ssh.close()
