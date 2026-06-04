import paramiko
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

def run(cmd, timeout=600):
    _, out, _ = cli.exec_command(cmd, timeout=timeout)
    return out.read().decode("utf-8", errors="replace")

# 用 -W ignore::DeprecationWarning 减少噪音
for test in [
    "tests/test_family_auth_mp_v1.py::TestInvitationAccept::test_tc08_accept_self_invite_blocked",
    "tests/test_health_archive_mgr_v1_20260529.py::test_benefits_cards_max_managed_label_updated",
]:
    print(f"\n========= {test} =========")
    o = run(
        f"docker exec {PROJECT_ID}-backend sh -c "
        f"\"cd /app && python -m pytest '{test}' --tb=long -W 'ignore::DeprecationWarning' 2>&1\" | tail -60",
        timeout=120,
    )
    print(o)

cli.close()
