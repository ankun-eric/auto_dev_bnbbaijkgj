import paramiko
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

def run(cmd, timeout=600):
    _, out, _ = cli.exec_command(cmd, timeout=timeout)
    return out.read().decode("utf-8", errors="replace")

print("=== full traceback ===")
o = run(
    f"docker exec {PROJECT_ID}-backend sh -c "
    f"\"cd /app && python -m pytest tests/test_health_archive_mgr_v1_20260529.py::test_benefits_cards_max_managed_label_updated --tb=long -W ignore 2>&1\" | grep -v Warning | tail -80",
    timeout=120,
)
print(o)
cli.close()
