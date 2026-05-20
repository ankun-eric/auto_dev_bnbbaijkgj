import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

cmd = (
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend bash -lc "
    "'cd /app && python -m pytest tests/test_page_navigate_external_url_fix_v1_20260519.py "
    "-v --tb=long --no-header 2>&1 | tail -n 250'"
)
_, stdout, stderr = cli.exec_command(cmd, timeout=300)
out = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
print(out)
if err:
    print("[stderr]", err)
cli.close()
