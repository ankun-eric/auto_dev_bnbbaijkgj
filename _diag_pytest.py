import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PASS='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PASS, timeout=30)
def run(cmd, t=600):
    print('>>>', cmd)
    _, o, e = cli.exec_command(cmd, timeout=t, get_pty=True)
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err: print('ERR:', err)
    print('rc=', o.channel.recv_exit_status())

# 显示测试详细错误（不 -x）
run(f'docker exec {DEPLOY_ID}-backend bash -lc \"cd /app && python -m pytest tests/test_bp_card_optimize_v1_20260530.py::test_bp_same_day_multiple_records_fully_preserved -v 2>&1 | tail -n 80\"')
run(f'docker exec {DEPLOY_ID}-backend bash -lc \"cd /app && python -m pytest tests/test_bp_tab_trend_v1_20260530.py::test_bp_history_returns_new_trend_fields -v 2>&1 | tail -n 80\"')
cli.close()
