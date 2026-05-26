import paramiko
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=20)
for q in [
    f'docker exec {TOKEN}-backend grep -nE "transfer/(pending|approve|reject|cancel)" /app/app/api/guardian_system_v12.py',
    f'docker exec {TOKEN}-backend sh -c "grep -E \\"transfer/\\" /app/app/api/guardian_system_v12.py"',
    f'docker exec {TOKEN}-h5 sh -c "ls /app/.next/static/chunks/app/health-profile/ && echo --- && cat /app/.next/static/chunks/app/health-profile/page-e1c792375e782c6a.js | head -c 1500"',
]:
    print(f"\n== {q}")
    _, so, _ = c.exec_command(q, timeout=30)
    out = so.read().decode("utf-8", errors="ignore")
    print(out[:3000])
c.close()
