import paramiko, sys
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888", timeout=60, look_for_keys=False, allow_agent=False)
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
cmd = (
    f"docker exec {DEPLOY_ID}-backend sh -c "
    "\"cd /app && python -m pytest tests/test_home_safety_gwid_ephone_v1.py::test_emergency_phone_format -v --tb=long 2>&1 | grep -E 'FAIL|assert|Error|response|invalid|400|201|200' | head -60\""
)
print(cmd)
stdin, stdout, stderr = cli.exec_command(cmd, timeout=120)
print(stdout.read().decode(errors="replace"))
print("STDERR:", stderr.read().decode(errors="replace"))
cli.close()
