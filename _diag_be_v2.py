"""诊断 backend 启动状态 + 安装 pytest 并运行测试"""
import paramiko
import time

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

    # 等 backend 起来
    time.sleep(5)
    run(c, f"cd {REMOTE_BASE} && docker compose ps")
    run(c, f"cd {REMOTE_BASE} && docker compose logs --tail=80 backend 2>&1 | tail -80")

    # 内网直连 backend
    run(c, "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend curl -s -o /dev/null -w '%{http_code}\\n' http://localhost:8000/health 2>&1 || true")
    run(c, "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend curl -s -o /dev/null -w '%{http_code}\\n' http://localhost:8000/docs 2>&1 || true")

    # 检查 pytest
    run(c, f"cd {REMOTE_BASE} && docker compose exec -T backend pip list 2>/dev/null | grep -i -E 'pytest|httpx|paramiko' | head -20")

    # 安装 pytest（如果没有）
    run(c, f"cd {REMOTE_BASE} && docker compose exec -T backend pip install pytest pytest-asyncio aiosqlite 2>&1 | tail -10")

    c.close()


if __name__ == "__main__":
    main()
