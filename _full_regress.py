"""跑更大范围的家族/健康档案/家庭管理测试集"""
import paramiko
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

def run(cmd, timeout=900):
    _, out, _ = cli.exec_command(cmd, timeout=timeout)
    return out.read().decode("utf-8", errors="replace")

TEST_FILES = [
    "tests/test_family.py",
    "tests/test_family_nickname_notnull_20260530.py",
    "tests/test_family_member_v2_20260518.py",
    "tests/test_family_member_state_machine_v1_20260529.py",
    "tests/test_family_management.py",
    "tests/test_member_family_member_v11_20260530.py",
    "tests/test_invite_family_card_v1_20260530.py",
    "tests/test_family_auth_mp_v1.py",
    "tests/test_family_invite_qrcode_fix.py",
    "tests/test_health_archive_mgr_v1_20260529.py",
]
test_args = " ".join(TEST_FILES)
print("=== 跑完整回归 ===")
o = run(
    f"docker exec {PROJECT_ID}-backend sh -c "
    f"'cd /app && python -m pytest {test_args} -v --tb=short -p no:cacheprovider 2>&1' | tail -120",
    timeout=900,
)
print(o)
cli.close()
