import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(cmd, timeout=120, retries=3):
    delay = 10
    last = None
    for attempt in range(retries):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, port=22, username=USER, password=PWD, timeout=30)
            stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=True)
            out = stdout.read().decode("utf-8", "replace")
            err = stderr.read().decode("utf-8", "replace")
            c.close()
            return out, err
        except Exception as e:
            last = e
            print(f"[retry {attempt+1}] {e}")
            time.sleep(delay)
            delay *= 2
    raise last


if __name__ == "__main__":
    cmds = [
        ("docker ps --format '{{.Names}}'", 60),
        (f"docker exec gateway-nginx sh -c 'grep -rn downloads /etc/nginx/ 2>/dev/null | head -50'", 90),
        (f"docker exec gateway-nginx sh -c 'grep -rn \"{DEPLOY_ID}\" /etc/nginx/ 2>/dev/null | head -50'", 90),
        ("docker exec gateway-nginx sh -c 'ls -la /data/static/apk/ 2>/dev/null | head -30'", 60),
    ]
    for cmd, to in cmds:
        print("\n========== CMD:", cmd)
        out, err = run(cmd, timeout=to)
        print(out)
        if err.strip():
            print("--- ERR ---")
            print(err)
