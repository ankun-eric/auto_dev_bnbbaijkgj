"""快速修复：将迁移源文件复制到容器内 /app/backend/app/services/ 位置，
再跑一次 pytest，确认 14/14 通过。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"


def run(client, cmd):
    print(f"$ {cmd}")
    _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=180)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("[stderr]", err)
    return out


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, 22, USER, PWD, timeout=20)
    try:
        run(client, f"docker exec {CONTAINER} mkdir -p /app/backend/app/services")
        run(client, f"docker exec {CONTAINER} cp /app/app/services/prd_tag_recommend_v1_migration.py /app/backend/app/services/prd_tag_recommend_v1_migration.py")
        run(client, f"docker exec {CONTAINER} ls -l /app/backend/app/services/")
        run(client, f"docker exec {CONTAINER} python -m pytest tests/test_tag_recommend_v1_20260520.py -v --tb=short --no-header 2>&1 | tail -25")
    finally:
        client.close()


if __name__ == "__main__":
    main()
