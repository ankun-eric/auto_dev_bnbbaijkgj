"""上传 _verify_rsa_in_container.py 到服务器并在 backend 容器中执行。"""
from __future__ import annotations

import os
import sys

import paramiko

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def run_ssh(client, cmd, timeout=300):
    print(f"\n>>> {cmd}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[:6000], flush=True)
    if err.strip():
        print(f"[STDERR] {err.strip()[:3000]}", flush=True)
    print(f"[EXIT {code}]", flush=True)
    return code, out, err


def main():
    workdir = os.path.dirname(os.path.abspath(__file__))
    local_script = os.path.join(workdir, "_verify_rsa_in_container.py")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=60)
    print("Connected.", flush=True)

    sftp = client.open_sftp()
    remote_path = f"{PROJECT_DIR}/_verify_rsa.py"
    sftp.put(local_script, remote_path)
    sftp.close()
    print(f"Uploaded {remote_path}", flush=True)

    backend_ct = f"{DEPLOY_ID}-backend"
    # 把脚本拷进容器再执行
    run_ssh(client, f"docker cp {remote_path} {backend_ct}:/tmp/_verify_rsa.py")
    code, out, _ = run_ssh(client,
        f"docker exec {backend_ct} python /tmp/_verify_rsa.py", timeout=120)

    client.close()
    sys.exit(0 if code == 0 else 2)


if __name__ == "__main__":
    main()
