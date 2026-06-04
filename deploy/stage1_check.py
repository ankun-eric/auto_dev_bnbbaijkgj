import paramiko
import sys

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def run_ssh(host, port, username, password, command, timeout=30):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=username, password=password, timeout=15)
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    exit_code = stdout.channel.recv_exit_status()
    client.close()
    return out, err, exit_code

def check_all():
    commands = {
        "项目目录检查": f"ls -la /home/ubuntu/{DEPLOY_ID}/ 2>/dev/null || echo '项目目录不存在'",
        "项目容器状态": f"docker ps -a --filter 'name={DEPLOY_ID}-' --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' 2>/dev/null",
        "Docker网络": f"docker network ls --filter 'name={DEPLOY_ID}-' --format '{{.Name}}' 2>/dev/null",
        "docker-compose检查": f"ls -la /home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml 2>/dev/null || echo 'docker-compose.prod.yml 不存在'",
        "gateway路由配置检查": f"cat /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf 2>/dev/null || echo 'gateway 路由配置不存在'",
    }

    for label, cmd in commands.items():
        print(f"\n=== {label} ===")
        out, err, code = run_ssh(HOST, PORT, USER, PASS, cmd)
        print(out)
        if err:
            print(f"[stderr] {err}")

if __name__ == "__main__":
    check_all()
