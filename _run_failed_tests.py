"""跑失败用例的详细 tb"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BE = f"{DEPLOY_ID}-backend"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=60,
            look_for_keys=False, allow_agent=False)

cmd = (
    f"docker exec {BE} sh -c 'cd /app && python -m pytest "
    f"tests/test_guardian_bugfix_v1_20260529.py::test_tc_del_05_full_cascade_delete_8_tables "
    f"tests/test_guardian_bugfix_v1_20260529.py::test_tc_list_01_removed_status_filtered "
    f"-v --tb=long --no-header -W ignore 2>&1 | tail -120'"
)
print(f"$ {cmd[:200]}")
_, stdout, _ = cli.exec_command(cmd, timeout=300)
print(stdout.read().decode(errors="replace"))
cli.close()
