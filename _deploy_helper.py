#!/usr/bin/env python3
"""SSH helper using paramiko."""
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"


def run(cmd, timeout=600):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30, banner_timeout=30)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    client.close()
    return rc, out, err


if __name__ == "__main__":
    cmd = sys.stdin.read() if len(sys.argv) < 2 else sys.argv[1]
    rc, out, err = run(cmd)
    if out:
        sys.stdout.write(out)
    if err:
        sys.stdout.write("\n--- STDERR ---\n" + err)
    sys.stdout.write(f"\n--- EXIT {rc} ---\n")
    sys.exit(0 if rc == 0 else 1)
