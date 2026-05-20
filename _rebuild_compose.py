"""rebuild admin-web 和 h5-web 镜像，因为它们是 standalone prod build"""
import paramiko, time, sys
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE=f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
cli=paramiko.SSHClient();cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com",username="ubuntu",password="Newbang888",timeout=120)
def sh(c,t=900,stream=True):
    si,so,se=cli.exec_command(c,timeout=t)
    out=[]
    for line in iter(so.readline,''):
        if stream:
            sys.stdout.write(line);sys.stdout.flush()
        out.append(line)
        if len(out)>4000:break
    ec=so.channel.recv_exit_status()
    return ''.join(out),se.read().decode(errors='replace'),ec

# 确保 host 上 src 是我们最新的（前面 tar 解压已经更新）
o,_,_=sh(f"ls -la /home/ubuntu/{DEPLOY_ID}/admin-web/src/app/'(admin)'/system/seed-import/",stream=False)
print("host file:",o)
o,_,_=sh(f"ls -la /home/ubuntu/{DEPLOY_ID}/h5-web/src/app/'(ai-chat)'/health-archive/ 2>&1",stream=False)
print("h5 old dir (期望不存在):",o.strip()[:200])

# rebuild admin-web
print("\n=== rebuild admin-web ===")
o,e,c=sh(f"cd /home/ubuntu/{DEPLOY_ID} && docker compose build admin-web 2>&1 | tail -50",t=900)
print("[exit]",c)

# rebuild h5-web (also need to delete old health-archive dir on host)
print("\n=== 删除 h5 旧 health-archive 目录 (host) ===")
o,_,_=sh(f"rm -rf /home/ubuntu/{DEPLOY_ID}/h5-web/src/app/'(ai-chat)'/health-archive && echo deleted_ok",stream=False)
print(o)

print("\n=== rebuild h5-web ===")
o,e,c=sh(f"cd /home/ubuntu/{DEPLOY_ID} && docker compose build h5-web 2>&1 | tail -50",t=900)
print("[exit]",c)

# up -d 重启
print("\n=== up -d admin-web h5-web ===")
o,e,c=sh(f"cd /home/ubuntu/{DEPLOY_ID} && docker compose up -d admin-web h5-web 2>&1",t=300)
print("[exit]",c)

print("等待 15 秒 ...");time.sleep(15)

# 烟测
def http(u):
    o,_,_=sh(f"curl -s -L -o /dev/null -w '%{{http_code}}' --max-time 30 '{u}'",stream=False)
    return o.strip()
print("\n=== HTTP smoke ===")
for tag,u in [
    ("/health-profile",f"{BASE}/health-profile"),
    ("/health-archive (期望404)",f"{BASE}/health-archive"),
    ("/admin/system/seed-import",f"{BASE}/admin/system/seed-import"),
    ("/admin/questionnaire-templates",f"{BASE}/admin/questionnaire-templates"),
    ("/api/admin/seed-packs (no auth)",f"{BASE}/api/admin/seed-packs"),
]:
    print(f"  {tag}: {http(u)}")
cli.close()
