"""
Bug 修复方案 v1.0：H5/admin 容器单容器重建部署驱动脚本。
- 上传 deploy_h5_admin_v2.sh + rollback_h5_admin_v2.sh 到服务器
- 依次执行 H5 / admin 部署；失败则脚本以 exit 1 终止（自动回滚已发生）
- 所有日志同步打印 + 写文件
"""
import os
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{TOKEN}"

LOCAL_FILES = [
    ("deploy_h5_admin_v2.sh", f"{REMOTE_DIR}/deploy_h5_admin_v2.sh"),
    ("rollback_h5_admin_v2.sh", f"{REMOTE_DIR}/rollback_h5_admin_v2.sh"),
]


def get_git_sha() -> str:
    import subprocess
    r = subprocess.run(["git", "rev-parse", "--short=10", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or "manual"


def run_remote(cli: paramiko.SSHClient, cmd: str, timeout: int = 900) -> int:
    print(f"\n$ {cmd}", flush=True)
    chan = cli.get_transport().open_session()
    chan.set_combine_stderr(True)
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    while True:
        if chan.recv_ready():
            data = chan.recv(65535).decode("utf-8", errors="ignore")
            if data:
                print(data, end="", flush=True)
        if chan.exit_status_ready():
            data = chan.recv(65535).decode("utf-8", errors="ignore")
            if data:
                print(data, end="", flush=True)
            break
        time.sleep(0.2)
    return chan.recv_exit_status()


def main():
    git_sha = get_git_sha()
    target = sys.argv[1] if len(sys.argv) > 1 else "both"  # h5 | admin | both
    print(f"[deploy_h5_admin_v2] git_sha={git_sha} target={target}")

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)

    sftp = cli.open_sftp()
    for local, remote in LOCAL_FILES:
        with open(local, "rb") as f:
            content = f.read()
        # 确保 LF 行结尾（防止 Windows CRLF 让 bash 报错）
        content = content.replace(b"\r\n", b"\n")
        with sftp.open(remote, "wb") as rf:
            rf.write(content)
        sftp.chmod(remote, 0o755)
        print(f"uploaded {local} -> {remote}")
    sftp.close()

    services = ["h5", "admin"] if target == "both" else [target]
    for svc in services:
        rc = run_remote(cli, f"cd {REMOTE_DIR} && bash deploy_h5_admin_v2.sh {git_sha} {svc}")
        if rc != 0:
            print(f"\n❌ deploy {svc} FAILED rc={rc}; rollback should have happened automatically.")
            cli.close()
            sys.exit(rc)

    cli.close()
    print("\n✅ all deploys SUCCESS")


if __name__ == "__main__":
    main()
