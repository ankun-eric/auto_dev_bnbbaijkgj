"""通过软链让前端静态测试找到 h5-web 源码并跑通。"""
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
backend = f"{DEPLOY_ID}-backend"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888", timeout=30)

cmd = (
    f"docker exec {backend} sh -c '"
    "ln -sfn /app/h5-web /h5-web && "
    "ln -sfn /app/miniprogram /miniprogram && "
    "cd /app && python -m pytest "
    "tests/test_sleep_all_history_fix_v1_20260602.py "
    "tests/test_metric_history_row_noaction_v1_20260602.py "
    "-v --tb=short --color=no 2>&1'"
)
_, stdout, _ = c.exec_command(cmd, timeout=600)
out = stdout.read().decode("utf-8", "replace")
lines = out.split("\n")
# 找 PASSED/FAILED 行 + summary
for ln in lines:
    if "PASSED" in ln or "FAILED" in ln or "SKIPPED" in ln or "ERROR" in ln or "===" in ln or "passed" in ln or "failed" in ln:
        print(ln)
c.close()
