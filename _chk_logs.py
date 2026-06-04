import paramiko
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

def run(cmd):
    _, out, err = cli.exec_command(cmd, timeout=120)
    return out.read().decode("utf-8", errors="replace"), err.read().decode("utf-8", errors="replace")

print("=== 后端启动日志（含 family/nickname/migrate/ERROR） ===")
o, e = run(f"docker logs --tail 400 {PROJECT_ID}-backend 2>&1 | grep -iE 'family|nickname|migrate|ERROR|Traceback' | head -120")
print(o)

print("=== 后端是否安装 pytest ===")
o, _ = run(f"docker exec {PROJECT_ID}-backend sh -c 'pip list 2>/dev/null | grep -i pytest'")
print(o)

print("=== 后端 /app 内容 ===")
o, _ = run(f"docker exec {PROJECT_ID}-backend sh -c 'ls /app/'")
print(o)

print("=== requirements 是否含 pytest ===")
o, _ = run(f"docker exec {PROJECT_ID}-backend sh -c 'cat /app/requirements.txt 2>/dev/null | head -30'")
print(o)

print("=== 检查 backend.Dockerfile ===")
o, _ = run(f"cat /home/ubuntu/{PROJECT_ID}/backend/Dockerfile")
print(o)

cli.close()
