"""快速 docker cp 测试文件 + 运行 pytest"""
import paramiko
HOST = "newbb.test.bangbangvip.com"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BE = f"{DEPLOY_ID}-backend"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, "ubuntu", "Newbang888", timeout=60, look_for_keys=False, allow_agent=False)
sftp = cli.open_sftp()
sftp.put("backend/tests/test_home_safety_gwid_ephone_v1.py",
         f"{PROJECT_DIR}/backend/tests/test_home_safety_gwid_ephone_v1.py")
sftp.close()
def run(cmd, timeout=900):
    print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    print(out[-5000:])
    return rc, out
run(f"docker cp {PROJECT_DIR}/backend/tests/test_home_safety_gwid_ephone_v1.py {BE}:/app/tests/test_home_safety_gwid_ephone_v1.py")
run(f"docker exec {BE} sh -c 'cd /app && python -m pytest "
    f"tests/test_home_safety_v1.py "
    f"tests/test_home_safety_v2.py "
    f"tests/test_home_safety_v2_revision.py "
    f"tests/test_home_safety_callback_schema_sync_v1.py "
    f"tests/test_home_safety_gwid_ephone_v1.py "
    f"-v --tb=short --no-header 2>&1 | tail -120'", timeout=600)
cli.close()
