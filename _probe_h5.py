"""探测 H5 实际访问路径"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://{HOST}/autodev/{DEPLOY_ID}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)

def run(cmd, timeout=60):
    print(f"$ {cmd}")
    _, out, err = c.exec_command(cmd, timeout=timeout)
    rc = out.channel.recv_exit_status()
    so = out.read().decode("utf-8", errors="replace")
    se = err.read().decode("utf-8", errors="replace")
    if so.strip(): print(so)
    if se.strip(): print(f"[stderr] {se}")
    return so

# 直接测试 H5 容器 + nginx
for path in ["", "/", "/h5", "/h5/", "/h5/ai-home", "/h5/ai-home/", "/h5/login"]:
    run(f"curl -s -o /dev/null -w 'GET {path} HTTP %{{http_code}} (redirect: %{{redirect_url}})\\n' '{BASE}{path}'")

# 检查 gateway 路由
print("\n--- gateway conf.d ---")
run(f"sudo cat /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf 2>/dev/null | head -80 || sudo cat /home/ubuntu/gateway/nginx.conf 2>/dev/null | grep -A 3 '{DEPLOY_ID}' | head -40")

c.close()
