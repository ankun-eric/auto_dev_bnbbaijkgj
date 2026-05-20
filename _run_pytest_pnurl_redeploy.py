"""仅重新部署测试文件并跑测试。"""
import io
import os
import tarfile
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/{USER}/{DEPLOY_ID}"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)

# tar test file
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as tf:
    tf.add(
        os.path.join(LOCAL_ROOT, "backend/tests/test_page_navigate_external_url_fix_v1_20260519.py"),
        arcname="backend/tests/test_page_navigate_external_url_fix_v1_20260519.py",
    )
buf.seek(0)

sftp = cli.open_sftp()
with sftp.open(f"{REMOTE_BASE}/_pnurl_tests.tar.gz", "wb") as f:
    f.write(buf.read())
sftp.close()

backend_container = f"{DEPLOY_ID}-backend"


def run(cmd, timeout=300):
    _, stdout, _ = cli.exec_command(cmd, timeout=timeout)
    o = stdout.read().decode("utf-8", errors="replace")
    print(o)
    return o


run(f"cd {REMOTE_BASE} && tar -xzf _pnurl_tests.tar.gz")
run(
    f"docker cp {REMOTE_BASE}/backend/tests/test_page_navigate_external_url_fix_v1_20260519.py "
    f"{backend_container}:/app/tests/test_page_navigate_external_url_fix_v1_20260519.py"
)
run(
    f"docker exec {backend_container} bash -lc "
    f"'cd /app && python -m pytest tests/test_page_navigate_external_url_fix_v1_20260519.py -v "
    f"--tb=short 2>&1 | grep -E \"PASSED|FAILED|ERROR|short test summary|test session starts|=========\" | head -n 40'"
)
cli.close()
