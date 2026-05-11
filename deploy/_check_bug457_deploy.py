"""[BUG-457] 查询服务器上当前 6b099ed3 项目的容器状态与对外路由"""
import paramiko
import sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(cmd: str) -> str:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=30)
    _, out, err = ssh.exec_command(cmd, timeout=60)
    o = out.read().decode("utf-8", errors="replace")
    e = err.read().decode("utf-8", errors="replace")
    ssh.close()
    return f"STDOUT:\n{o}\nSTDERR:\n{e}"


print("=== docker ps for project ===")
print(run(f"docker ps -a --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {PROJECT_ID} || echo NOT_FOUND"))

print("\n=== existing project dirs on server ===")
print(run(f"ls -la ~/autodev/{PROJECT_ID} 2>/dev/null || echo NO_DIR"))

print("\n=== gateway nginx conf for this project ===")
print(run(
    f"docker exec gateway-nginx ls /etc/nginx/conf.d/ 2>/dev/null | grep -i 6b099ed3 || "
    f"sudo find /home/ubuntu /opt /etc -name '*6b099ed3*' 2>/dev/null | head -20 || echo NOT_FOUND"
))
