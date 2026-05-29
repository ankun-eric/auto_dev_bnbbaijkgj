"""[PRD-BP-CARD-OPTIMIZE-V1] 在服务器后端容器内运行新增测试 + 回归 BUGFIX-BP-TAB-OPTIMIZE-V1。"""
import paramiko, os
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASS="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR=f"/home/ubuntu/{DEPLOY_ID}"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = cli.open_sftp()

# 同步测试文件到容器内
local_test = os.path.join(os.path.dirname(__file__), "backend", "tests", "test_bp_card_optimize_v1_20260530.py")
remote_test = f"{PROJECT_DIR}/backend/tests/test_bp_card_optimize_v1_20260530.py"
print(f"PUT {local_test} -> {remote_test}")
sftp.put(local_test, remote_test)
sftp.close()

def run(cmd, t=600):
    print(f"\n>>> {cmd}")
    _, o, e = cli.exec_command(cmd, timeout=t, get_pty=True)
    out = o.read().decode(errors='replace')
    err = e.read().decode(errors='replace')
    rc = o.channel.recv_exit_status()
    if out: print(out)
    if err: print('STDERR:', err)
    print(f"<<< rc={rc}")
    return rc, out

# 拷进容器
run(f"docker cp {PROJECT_DIR}/backend/tests/test_bp_card_optimize_v1_20260530.py {DEPLOY_ID}-backend:/app/tests/test_bp_card_optimize_v1_20260530.py")
# 同步关键 schemas/api 文件以确保后端测试基于最新（无变更但稳妥）
# 在容器中跑测试
run(f"docker exec {DEPLOY_ID}-backend bash -lc 'cd /app && python -m pytest tests/test_bp_card_optimize_v1_20260530.py -x -v 2>&1 | tail -n 100'", t=600)
# 回归：BUGFIX-BP-TAB-OPTIMIZE-V1 的测试集
run(f"docker cp {PROJECT_DIR}/backend/tests/test_bp_tab_trend_v1_20260530.py {DEPLOY_ID}-backend:/app/tests/test_bp_tab_trend_v1_20260530.py")
run(f"docker exec {DEPLOY_ID}-backend bash -lc 'cd /app && python -m pytest tests/test_bp_tab_trend_v1_20260530.py -x -v 2>&1 | tail -n 100'", t=600)

cli.close()
