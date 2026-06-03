"""回归测试：跑原有 home_safety 相关测试套件，确认本次 Bug 修复无破坏。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def conn():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    return c


def run(c, cmd, timeout=900):
    print(f"$ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    print(f"(rc={rc})\n")
    return rc, out, err


def main():
    c = conn()
    run(
        c,
        f"docker exec {DEPLOY_ID}-backend bash -lc "
        f"'cd /app && python -m pytest "
        f"tests/test_home_safety_v1.py "
        f"tests/test_home_safety_v2.py "
        f"tests/test_home_safety_v2_revision.py "
        f"tests/test_home_safety_gwid_ephone_v1.py "
        f"tests/test_home_safety_callback_schema_sync_v1.py "
        f"tests/test_home_safety_callback_datatype_v1.py "
        f"-v --tb=short 2>&1 | tail -120'",
        timeout=900,
    )


if __name__ == "__main__":
    main()
