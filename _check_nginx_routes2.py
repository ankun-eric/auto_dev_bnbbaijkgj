"""检查 gateway 容器的配置"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

def run(cmd, t=30):
    _, o, e = ssh.exec_command(cmd, timeout=t)
    return o.read().decode(), e.read().decode()

PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

print('=== docker inspect gateway 看挂载 ===')
o, _ = run("docker inspect gateway --format '{{json .Mounts}}' 2>/dev/null")
print(o[:2000])

print('=== gateway 容器内 /etc/nginx 树 ===')
o, _ = run("docker exec gateway sh -c 'find /etc/nginx -type f -name \"*.conf\" 2>/dev/null'")
print(o)

print(f'=== 找包含 {PROJECT_ID} 的文件 ===')
o, _ = run(f"docker exec gateway sh -c 'grep -rl \"{PROJECT_ID}\" /etc/nginx 2>/dev/null'")
print(o)
for f in o.strip().split('\n'):
    if f.strip():
        c, _ = run(f'docker exec gateway cat {f.strip()}')
        print(f'--- {f.strip()} ---')
        print(c[:3000])

ssh.close()
