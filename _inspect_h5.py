import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888")

cmds = [
    "docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 --format='{{json .Config.Env}}'",
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 ls /app/.next/server/app/autodev 2>&1 | head -5",
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 ls /app/.next/server/app/ 2>&1 | head -10",
    "curl -fsS -o /dev/null -w 'HTTP=%{http_code}\\n' 'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/'",
    "curl -fsS -o /dev/null -w 'HTTP=%{http_code}\\n' 'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'",
    "docker logs --tail 5 6b099ed3-7175-4a78-91f4-44570c84ed27-h5",
]
for c in cmds:
    print(f"$ {c}")
    _, out, err = ssh.exec_command(c, timeout=20)
    print(out.read().decode("utf-8", errors="ignore").rstrip())
    e = err.read().decode("utf-8", errors="ignore").rstrip()
    if e:
        print("ERR:", e)
    print("-" * 40)
ssh.close()
