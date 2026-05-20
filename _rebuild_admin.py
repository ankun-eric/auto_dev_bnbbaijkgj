"""admin 容器是 next standalone (prod)，需要重新 build 后再重启。
但是 standalone 模式下 build artifact 在 /app/.next，且容器层级独立。
直接尝试 docker exec npm run build 试试。
"""
import paramiko, time
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE=f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
cli=paramiko.SSHClient();cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com",username="ubuntu",password="Newbang888",timeout=60)
def sh(c,t=600):
    si,so,se=cli.exec_command(c,timeout=t)
    return so.read().decode(errors='replace'),se.read().decode(errors='replace'),so.channel.recv_exit_status()

# 先看 admin 容器的镜像/状态
o,_,_=sh("docker images --format '{{.Repository}}:{{.Tag}}' | grep -i admin | head -5")
print("admin images:",o.strip())
o,_,_=sh(f"docker inspect {DEPLOY_ID}-admin --format '{{{{.Config.Image}}}}'")
print("admin uses image:",o.strip())

# 检查容器内有 package.json + node_modules?
o,_,_=sh(f"docker exec {DEPLOY_ID}-admin sh -c 'ls /app/package.json /app/node_modules 2>&1 | head -5'")
print("admin /app structure:",o)

# 如果有 src 源码 + package.json，能否 next build？
o,e,c=sh(f"docker exec {DEPLOY_ID}-admin sh -c 'cd /app && ls /app && cat /app/package.json 2>&1 | head -30'",t=30)
print("--- /app contents and package.json head ---");print(o[:2000])

cli.close()
