"""Helper for SSH/SCP deploy of glucose v1 changes."""
import paramiko
import sys
import os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"


def get_ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
    return c


def run(cmd, timeout=120):
    c = get_ssh()
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return code, out, err
    finally:
        c.close()


def put_file(local, remote):
    c = get_ssh()
    try:
        sftp = c.open_sftp()
        # ensure dir exists
        d = os.path.dirname(remote).replace("\\", "/")
        # try mkdir -p via exec
        c.exec_command(f"mkdir -p {d}")
        sftp.put(local, remote)
        sftp.close()
    finally:
        c.close()


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "run":
        cmd = sys.argv[2]
        timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 120
        code, out, err = run(cmd, timeout=timeout)
        print(f"--- EXIT {code} ---")
        if out:
            print("--- STDOUT ---")
            print(out)
        if err:
            print("--- STDERR ---")
            print(err)
        sys.exit(code)
    elif action == "put":
        local = sys.argv[2]
        remote = sys.argv[3]
        put_file(local, remote)
        print(f"OK uploaded {local} -> {remote}")
