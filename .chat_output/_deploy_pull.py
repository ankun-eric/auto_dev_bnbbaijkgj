"""Deploy: pull latest from git on server, rebuild backend + admin-web + h5-web docker."""
import paramiko
import sys
import time

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
REMOTE_DIR = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
GIT_URL = 'https://ankun-eric:${GITHUB_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git'


def exec_ssh(ssh, cmd, timeout=900, show=True):
    if show:
        print(f"  $ {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if show:
        if out.strip():
            print(f"    stdout: {out[-1500:]}")
        if err.strip():
            print(f"    stderr: {err[-1500:]}")
        print(f"    exit: {exit_code}")
    return exit_code, out, err


def main():
    print(f"Connecting to {HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    print("\n[1] Check existing remote dir + git status")
    exec_ssh(ssh, f"ls -la {REMOTE_DIR} 2>/dev/null | head -30")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && git rev-parse HEAD 2>&1")

    print("\n[2] Stash any local server changes + git pull origin master")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && git config --global --add safe.directory {REMOTE_DIR}")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && git stash --include-untracked 2>&1 || true")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && git remote set-url origin {GIT_URL}")
    # Retry fetch up to 5 times for transient TLS errors
    success = False
    for i in range(5):
        code, out, err = exec_ssh(ssh,
            f"cd {REMOTE_DIR} && git -c http.postBuffer=524288000 fetch origin master 2>&1",
            timeout=300)
        if code == 0:
            success = True
            break
        print(f"  Retry {i+1}/5 fetch failed, sleeping 10s...")
        time.sleep(10)
    if not success:
        print("git fetch failed after retries, aborting")
        sys.exit(1)
    exec_ssh(ssh, f"cd {REMOTE_DIR} && git reset --hard origin/master 2>&1")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && git log -1 --oneline")

    print("\n[3] List docker compose services")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && docker compose ps 2>&1 | head -30")

    print("\n[4] Rebuild backend + admin-web + h5-web (services with code changes)")
    code, out, err = exec_ssh(ssh,
        f"cd {REMOTE_DIR} && docker compose build backend admin-web h5-web 2>&1 | tail -100",
        timeout=1800)
    if code != 0:
        print("Build failed, aborting")
        sys.exit(2)

    print("\n[5] Restart services")
    exec_ssh(ssh,
        f"cd {REMOTE_DIR} && docker compose up -d backend admin-web h5-web 2>&1 | tail -30",
        timeout=600)

    print("\n[6] Wait for healthy + check container status")
    time.sleep(20)
    exec_ssh(ssh, f"cd {REMOTE_DIR} && docker compose ps 2>&1 | head -30")

    print("\n[7] Tail backend logs")
    exec_ssh(ssh, f"cd {REMOTE_DIR} && docker compose logs --tail 80 backend 2>&1 | tail -100")

    ssh.close()
    print("\n[OK] deploy_pull complete")


if __name__ == '__main__':
    main()
