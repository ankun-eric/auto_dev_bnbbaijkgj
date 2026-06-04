import paramiko
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

def run(cmd, timeout=600):
    _, out, _ = cli.exec_command(cmd, timeout=timeout)
    return out.read().decode("utf-8", errors="replace")

# 看具体失败原因
print("=== tc06/07/08 失败详情 ===")
o = run(
    f"docker exec {PROJECT_ID}-backend sh -c "
    "'cd /app && python -m pytest tests/test_family_auth_mp_v1.py::TestInvitationAccept::test_tc06_accept_with_partial_merge_fields "
    "tests/test_family_auth_mp_v1.py::TestInvitationAccept::test_tc07_accept_without_body_backcompat "
    "tests/test_family_auth_mp_v1.py::TestInvitationAccept::test_tc08_accept_self_invite_blocked "
    "-v --tb=short 2>&1' | tail -80",
    timeout=120,
)
print(o)

print("=== test_health_archive_mgr_v1_20260529::test_benefits_cards_max_managed_label_updated ===")
o = run(
    f"docker exec {PROJECT_ID}-backend sh -c "
    "'cd /app && python -m pytest tests/test_health_archive_mgr_v1_20260529.py::test_benefits_cards_max_managed_label_updated -v --tb=short 2>&1' | tail -60",
    timeout=120,
)
print(o)

print("=== test_family_management 第一个 ERROR ===")
o = run(
    f"docker exec {PROJECT_ID}-backend sh -c "
    "'cd /app && python -m pytest tests/test_family_management.py::TestInvitationCRUD::test_tc001_create_invitation_success -v --tb=long 2>&1' | tail -80",
    timeout=120,
)
print(o)

print("=== test_family_invite_qrcode_fix ERROR ===")
o = run(
    f"docker exec {PROJECT_ID}-backend sh -c "
    "'cd /app && python -m pytest tests/test_family_invite_qrcode_fix.py::TestInvitationDetail::test_invitation_get_details -v --tb=long 2>&1' | tail -60",
    timeout=120,
)
print(o)

cli.close()
