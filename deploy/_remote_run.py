"""Run a remote command via paramiko, prints stdout/stderr/exit_code."""
import sys
import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"


def connect(retries=4, backoff=8):
    last = None
    for i in range(retries):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(HOST, username=USER, password=PWD,
                        timeout=30, banner_timeout=30, auth_timeout=30)
            return ssh
        except Exception as e:
            last = e
            print(f"[ssh] retry {i+1}: {e}", flush=True)
            time.sleep(backoff)
    raise last


def run(cmd, timeout=600):
    ssh = connect()
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
        out = stdout.read().decode('utf-8', 'replace')
        err = stderr.read().decode('utf-8', 'replace')
        code = stdout.channel.recv_exit_status()
        return out, err, code
    finally:
        ssh.close()


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else "echo hello"
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    o, e, c = run(cmd, timeout)
    if o:
        sys.stdout.write(o)
    if e:
        sys.stderr.write("[STDERR]\n" + e)
    sys.exit(c)
