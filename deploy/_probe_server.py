"""探测服务器部署方式与实际项目路径。"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

cmds = [
    "ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 | head -30",
    "ls /home/ubuntu/ | head -20",
    "docker ps --format 'table {{.Names}}\\t{{.Status}}' | head -30",
    "find /home/ubuntu -maxdepth 3 -name '.git' -type d 2>/dev/null | head",
    "find /home/ubuntu -maxdepth 4 -name 'docker-compose*.yml' 2>/dev/null | head",
]

for c in cmds:
    print(f"\n$ {c}")
    _, out, err = ssh.exec_command(c, timeout=30)
    print(out.read().decode(errors='ignore'))
    e = err.read().decode(errors='ignore')
    if e.strip():
        print(f"[ERR] {e}")

ssh.close()
