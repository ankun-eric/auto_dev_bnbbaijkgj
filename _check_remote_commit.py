import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASS="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PASS, timeout=30)
for c in [
    f"cd /home/ubuntu/{DEPLOY_ID} && git log -3 --oneline",
    f"cd /home/ubuntu/{DEPLOY_ID} && grep -c 'PRD-BP-CARD-OPTIMIZE-V1' h5-web/src/app/health-metric/\\[type\\]/page.tsx 2>&1",
    f"cd /home/ubuntu/{DEPLOY_ID} && grep -c 'bp-action-row\\|bp-action-manual\\|bp-action-bind' h5-web/src/app/health-metric/\\[type\\]/page.tsx 2>&1",
    f"cd /home/ubuntu/{DEPLOY_ID} && grep -c 'bp-mini-capsule\\|bp-mini-time-source' h5-web/src/app/health-profile/page.tsx 2>&1",
]:
    print('>>>', c)
    _, o, e = cli.exec_command(c, timeout=120)
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err: print('ERR:', err)
cli.close()
