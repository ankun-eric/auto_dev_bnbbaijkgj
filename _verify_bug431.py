"""[Bug-431] 远程验证（v3，BusyBox grep 无 --include，改 find -exec）。"""
import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASSWORD="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PASSWORD, timeout=30)

CMDS = [
    # 1. 旧 sticky 顶栏 CSS 是否清理（构建产物中应为 0 计数）
    f"docker exec {DEPLOY_ID}-h5 sh -c \"find /app/.next/server -path '*ai-home*' -name 'page.js' | xargs grep -c 'sticky top-0 z-50' 2>/dev/null\"",
    # 2. fab / collapse-btn testid 是否进入构建产物
    f"docker exec {DEPLOY_ID}-h5 sh -c \"find /app/.next/server -path '*ai-home*' -name 'page.js' | xargs grep -o -E 'ai-home-top-panel-fab|ai-home-top-panel-collapse-btn' 2>/dev/null | sort -u\"",
    # 3. setSentInSession 计数
    f"docker exec {DEPLOY_ID}-h5 sh -c \"find /app/.next/server -path '*ai-home*' -name 'page.js' | xargs grep -c 'sentInSession' 2>/dev/null\"",
    # 4. position fixed 顶栏标识：搜整个产物
    f"docker exec {DEPLOY_ID}-h5 sh -c \"find /app/.next/server -path '*ai-home*' -name 'page.js' | xargs grep -c 'position:\\\"fixed\\\"' 2>/dev/null\"",
]
for c in CMDS:
    print(f"\n>>> {c[:240]}")
    _, out, err = ssh.exec_command(c, timeout=60)
    print(out.read().decode("utf-8","replace"))
    e = err.read().decode("utf-8","replace")
    if e: print("STDERR:", e[:400])
ssh.close()
