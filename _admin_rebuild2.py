"""试着 docker exec rebuild admin"""
import paramiko, time
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE=f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
cli=paramiko.SSHClient();cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com",username="ubuntu",password="Newbang888",timeout=60)
def sh(c,t=900):
    si,so,se=cli.exec_command(c,timeout=t)
    return so.read().decode(errors='replace'),se.read().decode(errors='replace'),so.channel.recv_exit_status()

# 切换 admin 到 dev 模式：直接 docker exec 启 next dev，绕过 server.js
# 更简单的方法：用 ext sidecar 跑 build，把生成的 .next 拷回去
# 最简单：让 admin 容器跑 dev mode 试试 - 但容器只装了 @next/@swc，没装其他依赖

# 看 server.js 是不是 standalone 的 server.js
o,_,_=sh(f"docker exec {DEPLOY_ID}-admin sh -c 'head -20 /app/server.js'")
print("--- server.js head ---");print(o)

# 看 .next 目录情况
o,_,_=sh(f"docker exec {DEPLOY_ID}-admin sh -c 'ls -la /app/.next/ 2>/dev/null; echo ---; ls /app/.next/server/app/ 2>/dev/null'")
print("--- .next contents ---");print(o[:2000])

# 如果不能 rebuild，那需要重建 image。先看 compose 文件
o,_,_=sh(f"find /home/ubuntu/{DEPLOY_ID} -name 'docker-compose*' -o -name 'Dockerfile*' 2>/dev/null | head -10")
print("--- compose/dockerfile 位置 ---");print(o)
o,_,_=sh(f"cat /home/ubuntu/{DEPLOY_ID}/docker-compose.yml 2>/dev/null | head -100")
print("--- docker-compose.yml head ---");print(o[:3000])
cli.close()
