"""仅运行 backend 容器内的测试"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DEPLOY_ID}"


def run(c, cmd, t=600):
    print(f"$ {cmd}")
    _, o, e = c.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    rc = o.channel.recv_exit_status()
    if out.strip():
        print(out)
    if err.strip():
        print("[err]", err)
    return out, err, rc


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    test_cmd = (
        f"cd {REMOTE_BASE} && docker compose exec -T backend "
        f"python -m pytest tests/test_home_safety_v1.py tests/test_home_safety_v2_revision.py "
        f"-v --tb=short 2>&1 | tail -200"
    )
    run(c, test_cmd, t=600)
    c.close()


if __name__ == "__main__":
    main()
