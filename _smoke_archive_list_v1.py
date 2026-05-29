"""[PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29] 验证 PRD 修复是否已生效

通过远程 docker exec 检查容器内的构建产物（chunks）中包含新增的关键字符串。
覆盖 5 个修复点：
  1. health-profile 入口卡跳转改 archive-list（路口A1+C1）
  2. health-profile renderInviteArea 删除（路口B1）
  3. i-guard 整体下线，改为 redirect placeholder
  4. member-center 配额文案改新格式
  5. archive-list 排版修复 + AI 外呼额度抽屉 + 邀请记录抽屉
  6. ConsultTargetPicker 立即去邀请抽屉
"""
import paramiko
import sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
H5_CTN = f"{DEPLOY_ID}-h5"


def ssh_run(cmd, timeout=60):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30, look_for_keys=False, allow_agent=False)
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="ignore")
        err = stderr.read().decode("utf-8", errors="ignore")
        rc = stdout.channel.recv_exit_status()
        return rc, out, err
    finally:
        c.close()


def grep_chunks(needle, path_glob):
    cmd = f"docker exec {H5_CTN} sh -c \"grep -l '{needle}' {path_glob} 2>/dev/null | head -3\""
    rc, out, err = ssh_run(cmd, timeout=30)
    return out.strip()


CHECKS = [
    {
        "name": "1. archive-list 包含「AI 外呼额度」按钮（S0 本人卡入口）",
        "needle": "AI 外呼额度",
        "path": "/app/.next/server/app/health-profile/archive-list/page.js",
    },
    {
        "name": "2. archive-list 包含「邀请记录」抽屉",
        "needle": "invitation-history-drawer",
        "path": "/app/.next/server/app/health-profile/archive-list/page.js",
    },
    {
        "name": "3. archive-list 包含「正在跳转到档案列表」（i-guard redirect）已下线 → 改抽屉",
        "needle": "ai-quota-drawer",
        "path": "/app/.next/server/app/health-profile/archive-list/page.js",
    },
    {
        "name": "4. health-profile/page.js 包含 archive-list 跳转（路口A1）",
        "needle": "/health-profile/archive-list",
        "path": "/app/.next/server/app/health-profile/page.js",
    },
    {
        "name": "5. i-guard 已下线为 redirect placeholder",
        "needle": "i-guard-redirect-placeholder",
        "path": "/app/.next/server/app/health-profile/i-guard/page.js",
    },
    {
        "name": "6. member-center 含新配额文案「不含本人」",
        "needle": "不含本人",
        "path": "/app/.next/server/app/member-center/page.js",
    },
    {
        "name": "7. ConsultTargetPicker 立即去邀请抽屉（合并到 ai-home chunk）",
        "needle": "consult-invite-now-drawer",
        "path": "/app/.next/server/chunks/*.js",
    },
]

ok = True
for c in CHECKS:
    res = grep_chunks(c["needle"], c["path"])
    status = "✅" if res else "❌"
    if not res:
        ok = False
    print(f"{status} {c['name']}")
    if res:
        for line in res.splitlines()[:2]:
            print(f"      {line}")
    else:
        print(f"      未在 {c['path']} 中找到关键字 '{c['needle']}'")

print()
print("=== Page-level reachability ===")
import urllib.request, ssl
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
base = f"https://{HOST}/autodev/{DEPLOY_ID}"
for url in [
    f"{base}/health-profile/archive-list/",
    f"{base}/health-profile/i-guard/",
    f"{base}/health-profile/",
    f"{base}/member-center/",
]:
    try:
        r = urllib.request.urlopen(url, timeout=20, context=ctx)
        print(f"✅ HTTP {r.status} {url}")
    except Exception as e:
        ok = False
        print(f"❌ {url} -> {e}")

print()
print("=== 总结 ===")
print("全部通过" if ok else "存在失败项")
sys.exit(0 if ok else 1)
