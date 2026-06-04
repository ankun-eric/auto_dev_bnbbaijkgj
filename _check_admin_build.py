import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def conn():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    return c


def run(c, cmd, timeout=600):
    print(f"$ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out[-4000:]:
        print(out[-4000:])
    if err[-2000:]:
        print("STDERR:", err[-2000:])
    print(f"(rc={rc})\n")
    return rc, out, err


def main():
    c = conn()
    proj = f"/home/ubuntu/{DEPLOY_ID}"
    run(c, f"ls -la {proj}/admin-web | head -30")
    run(c, f"ls -la {proj}/admin-web/Dockerfile* 2>&1 || true")
    run(c, f"ls -la {proj}/docker-compose*.yml 2>&1 | head -20")
    run(c, f"cat {proj}/admin-web/Dockerfile 2>&1 | head -80 || true")


if __name__ == "__main__":
    main()
