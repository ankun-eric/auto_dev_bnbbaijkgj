"""Probe server for static asset directory used by miniprogram/H5."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(cmd: str) -> str:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out)
    if err:
        print("[stderr]", err)
    return out


run(f"ls -la {PROJECT_DIR}/")
run(f"ls -la {PROJECT_DIR}/static/ 2>/dev/null | head -30")
run(f"ls -la {PROJECT_DIR}/public/ 2>/dev/null | head -30")
run(f"find {PROJECT_DIR} -maxdepth 3 -type f \\( -name '*.zip' -o -name '*.apk' -o -name '*.ipa' \\) 2>/dev/null")
run(f"find {PROJECT_DIR} -maxdepth 2 -type d 2>/dev/null")
run(f"docker ps --format 'table {{{{.Names}}}}\\t{{{{.Image}}}}\\t{{{{.Ports}}}}' | grep -i 6b099ed3 || true")

ssh.close()
print("\nDONE")
