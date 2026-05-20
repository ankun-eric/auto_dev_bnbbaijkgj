"""清理 Next.js 缓存并彻底重启 h5/admin 容器"""
import paramiko, time
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

def sh(cli, cmd, t=180):
    si, so, se = cli.exec_command(cmd, timeout=t)
    return so.read().decode(errors='replace'), se.read().decode(errors='replace'), so.channel.recv_exit_status()

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=60)
try:
    for svc in ("admin", "h5"):
        c = f"{DEPLOY_ID}-{svc}"
        # 清理 .next 缓存
        o,e,_ = sh(cli, f"docker exec {c} sh -c 'rm -rf /app/.next/cache 2>/dev/null; rm -rf /app/.next/server/app/\\(ai-chat\\)/health-archive 2>/dev/null; echo ok'")
        print(f"[{svc}] cache cleanup:", o.strip())
        o,e,_ = sh(cli, f"docker restart {c}")
        print(f"[{svc}] restart:", o.strip())
    print("等待 25 秒让 next dev 启动...")
    time.sleep(25)
    # 再次烟测
    for tag, u in [
        ("/health-profile (新)", f"{BASE}/health-profile"),
        ("/health-archive (旧,期望404)", f"{BASE}/health-archive"),
        ("/admin/system/seed-import", f"{BASE}/admin/system/seed-import"),
        ("/admin/questionnaire-templates", f"{BASE}/admin/questionnaire-templates"),
    ]:
        o,_,_ = sh(cli, f"curl -s -L -o /dev/null -w '%{{http_code}}' --max-time 30 '{u}'")
        print(f"  {tag}: {o.strip()}")
finally:
    cli.close()
