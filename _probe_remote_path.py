"""快速探索远程服务器目录"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PASS)

cmds = [
    "ls /home/ubuntu/",
    "ls / | head -20",
    f"find / -type d -name '{DEPLOY_ID}*' 2>/dev/null | head -10",
    f"docker ps --format '{{{{.Names}}}}' | grep {DEPLOY_ID[:8]}",
    f"docker inspect {DEPLOY_ID}-backend --format '{{{{ .Mounts }}}}' 2>&1 | head -20",
]
for c in cmds:
    print(f"\n>>> {c}")
    stdin, stdout, stderr = cli.exec_command(c)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)

cli.close()
