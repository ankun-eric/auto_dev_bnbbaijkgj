"""单独跑一次 admin-web build，抓全量错误信息"""
import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PASSWORD, timeout=30)
stdin, stdout, stderr = c.exec_command(
    f"cd {PROJECT_DIR} && docker compose build admin-web 2>&1 | tail -400",
    timeout=900,
)
out = stdout.read().decode("utf-8", errors="replace")
print(out)
c.close()
