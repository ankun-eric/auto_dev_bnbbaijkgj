"""Quick pull latest commit on server (no rebuild needed since flutter only)."""
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
REMOTE_DIR = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(cmd, t=120):
    print(f"$ {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=t)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out[:500])
    if err.strip() and "Warning" not in err:
        print("STDERR:", err[:500])
    print(f"  exit: {rc}")
    return rc


for i in range(5):
    rc = run(f"cd {REMOTE_DIR} && git fetch origin master 2>&1", t=180)
    if rc == 0:
        break
    import time
    time.sleep(10)
run(f"cd {REMOTE_DIR} && git reset --hard origin/master 2>&1")
run(f"cd {REMOTE_DIR} && git log -1 --oneline")

ssh.close()
