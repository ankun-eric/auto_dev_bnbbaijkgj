"""通过 SSH 找服务器上能从 base URL 访问到的静态文件路径（快速版）"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

def run(cmd, t=60):
    _, o, e = ssh.exec_command(cmd, timeout=t)
    return o.read().decode(), e.read().decode()

PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

print('=== 1) 在已知部署目录树下找 miniprogram zip ===')
for d in [f'/home/ubuntu/autodev/{PROJECT_ID}', f'/home/ubuntu/{PROJECT_ID}', f'/var/www/autodev/{PROJECT_ID}']:
    o, _ = run(f'find {d} -maxdepth 4 -name "miniprogram_*.zip" 2>/dev/null | head -10')
    if o.strip():
        print(f'--- {d} ---')
        print(o)

print('=== 2) gateway-nginx 配置 grep autodev / project id ===')
o, _ = run(f"docker exec gateway-nginx sh -c 'grep -rl {PROJECT_ID} /etc/nginx/ 2>/dev/null'")
print(o)

print('=== 3) gateway-nginx 配置 cat ===')
o, _ = run(f"docker exec gateway-nginx sh -c 'find /etc/nginx -name \"*{PROJECT_ID}*\" 2>/dev/null'")
print(o)
if o.strip():
    for f in o.strip().split('\n'):
        o2, _ = run(f"docker exec gateway-nginx cat {f.strip()}")
        print(f'--- {f.strip()} ---')
        print(o2[:3000])

ssh.close()
