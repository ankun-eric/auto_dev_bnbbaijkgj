"""SSH helper for home 3bugs deployment to newbb.test.bangbangvip.com."""
import paramiko
import sys
import time

SERVER = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
SUDO_PREFIX = f'echo "{PASSWORD}" | sudo -S '


def get_client():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh, command, timeout=600, silent=False):
    if not silent:
        print(f">>> {command}")
    stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if not silent:
        if out.strip():
            print(out)
        if err.strip():
            print(f"STDERR: {err}")
        print(f"[exit={code}]")
        print("---")
    return code, out, err


def run_script(commands, timeout=600):
    ssh = get_client()
    try:
        results = []
        for c in commands:
            results.append(run(ssh, c, timeout=timeout))
        return results
    finally:
        ssh.close()


if __name__ == "__main__":
    cmd = " ".join(sys.argv[1:])
    if cmd:
        ssh = get_client()
        try:
            run(ssh, cmd)
        finally:
            ssh.close()
