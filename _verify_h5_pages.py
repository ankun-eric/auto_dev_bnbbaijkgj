import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PASS='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PASS, timeout=30)
def run(cmd, t=120):
    print('>>>', cmd)
    _, o, e = cli.exec_command(cmd, timeout=t, get_pty=True)
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err: print('ERR:', err)
BASE = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'
for path in ['/', '/health-profile/', '/health-metric/blood_pressure/', '/login']:
    run("curl -sSI -L --max-redirs 3 -o /dev/null -w 'final=%{http_code} url=%{url_effective}\\n' '" + BASE + path + "'")
# 抓详情页 HTML，验证关键 data-testid 已被打入 chunk
run("curl -sSL '" + BASE + "/health-metric/blood_pressure/' | grep -o 'bp-action-row\\|bp-action-manual\\|bp-action-bind\\|bp-trend-card\\|bp-status-card\\|bp-mini-capsule\\|PRD-BP-CARD-OPTIMIZE-V1' | sort -u")
# 首页 HTML 查 testid（首屏即为 health-profile/page，但页面较大且 data-testid 多在客户端 chunk）
run("curl -sSL '" + BASE + "/health-profile/' | grep -o 'bp-mini-capsule\\|bp-mini-time-source\\|prd469-metric-blood_pressure' | sort -u")
cli.close()
