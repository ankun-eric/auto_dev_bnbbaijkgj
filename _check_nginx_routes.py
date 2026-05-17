"""检查 gateway-nginx 配置，找静态文件路由"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

def run(cmd, t=30):
    _, o, e = ssh.exec_command(cmd, timeout=t)
    return o.read().decode(), e.read().decode()

PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

print('=== 1) gateway 容器列表 ===')
o, _ = run("docker ps --format '{{.Names}}' | sort")
print(o)

print('=== 2) 进 gateway-nginx 看 conf 包含 6b099 的文件 ===')
o, _ = run(f"docker exec gateway-nginx grep -rl '{PROJECT_ID}' /etc/nginx/ 2>/dev/null")
print(o)
for f in o.strip().split('\n'):
    if f.strip():
        c, _ = run(f'docker exec gateway-nginx cat {f.strip()}')
        print(f'--- {f.strip()} ---')
        print(c)
        print()

print('=== 3) /etc/nginx/conf.d 全部 *.conf 文件 ===')
o, _ = run("docker exec gateway-nginx ls /etc/nginx/conf.d/ 2>/dev/null")
print(o)

ssh.close()
