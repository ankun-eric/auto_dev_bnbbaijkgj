"""SSH helper for remote diagnose/deploy. Reads commands from argv[1] file or stdin."""
import sys, os, paramiko, time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"


def run(cmd, timeout=120):
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    chan = cli.get_transport().open_session()
    chan.set_combine_stderr(True)
    chan.exec_command(cmd)
    out = b""
    start = time.time()
    while True:
        if chan.recv_ready():
            out += chan.recv(65536)
        if chan.exit_status_ready() and not chan.recv_ready():
            break
        if time.time() - start > timeout:
            chan.close()
            cli.close()
            return -1, out.decode("utf-8", errors="replace") + "\n[TIMEOUT]"
        time.sleep(0.05)
    while chan.recv_ready():
        out += chan.recv(65536)
    rc = chan.recv_exit_status()
    cli.close()
    return rc, out.decode("utf-8", errors="replace")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
    else:
        cmd = sys.stdin.read()
    timeout = int(os.environ.get("SSH_TIMEOUT", "120"))
    rc, out = run(cmd, timeout=timeout)
    sys.stdout.write(out)
    sys.stdout.write(f"\n[exit={rc}]\n")
    sys.exit(0 if rc == 0 else 1)
