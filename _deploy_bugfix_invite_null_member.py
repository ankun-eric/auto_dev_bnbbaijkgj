"""[BUG-FIX-INVITE-NULL-MEMBER 2026-05-25] 远程部署修复版。

流程：
1. 通过 SSH 检查服务器上是否已有项目目录
2. 上传修改的文件（backend、h5-web）
3. 执行 DB schema 迁移 SQL
4. 重启 backend、h5-web 容器
5. 检查容器健康

使用 paramiko 操作 SSH/SFTP，避免依赖外部 sshpass。
"""

import os
import posixpath
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"

LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

# 本次需要上传的文件（基于本次 Bug 修复，只传改动的核心源文件）
FILES_TO_UPLOAD = [
    "backend/app/models/models.py",
    "backend/app/api/family_management.py",
    "backend/app/api/family.py",
    "backend/migrations/migration_invite_nullable_member_id_20260525.sql",
    "backend/tests/test_invite_no_phantom_tab_20260525.py",
    "h5-web/src/app/health-profile/page.tsx",
]


def make_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    return client


def run(client, cmd, timeout=120):
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out.rstrip())
    if err:
        print(f"[stderr] {err.rstrip()}")
    print(f"[exit={rc}]")
    return rc, out, err


def sftp_put(sftp, local_path, remote_path):
    # 确保远程目录存在
    remote_dir = posixpath.dirname(remote_path)
    parts = remote_dir.strip("/").split("/")
    cur = ""
    for p in parts:
        cur = cur + "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass
    sftp.put(local_path, remote_path)
    print(f"  uploaded: {local_path} -> {remote_path}")


def main():
    print(f"[deploy] connecting to {USER}@{HOST}:{PORT}")
    client = make_client()
    try:
        # 0) 检查项目目录
        rc, out, _ = run(client, f"test -d {REMOTE_ROOT} && echo OK || echo MISSING")
        if "MISSING" in out:
            print(f"[fatal] remote project dir not found: {REMOTE_ROOT}")
            return 2

        # 1) 上传文件
        print("\n[step 1] upload files")
        sftp = client.open_sftp()
        try:
            for rel in FILES_TO_UPLOAD:
                local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
                remote = posixpath.join(REMOTE_ROOT, rel)
                if not os.path.isfile(local):
                    print(f"  [skip] missing local file: {local}")
                    continue
                sftp_put(sftp, local, remote)
        finally:
            sftp.close()

        # 2) DB 迁移：member_id 改为 NULLABLE
        print("\n[step 2] DB schema sync: family_invitations.member_id -> NULL")
        sql = "ALTER TABLE family_invitations MODIFY COLUMN member_id INT NULL;"
        run(
            client,
            f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 -e \"USE bini_health; {sql}\" 2>&1 | tail -n 5",
            timeout=60,
        )

        # 3) 重启 backend（backend 是直接挂载源代码运行，restart 即可生效）
        print("\n[step 3] restart backend container")
        run(client, f"cd {REMOTE_ROOT} && docker compose -f docker-compose.prod.yml restart backend", timeout=180)

        # 4) 重新构建 h5-web（前端代码变更需要 rebuild）
        print("\n[step 4] rebuild h5-web container")
        rc, out, err = run(
            client,
            f"cd {REMOTE_ROOT} && docker compose -f docker-compose.prod.yml up -d --build h5-web 2>&1 | tail -n 80",
            timeout=900,
        )
        if rc != 0:
            print("[warn] h5-web rebuild non-zero exit code, will continue and verify")

        # 5) 等待容器就绪
        print("\n[step 5] wait for containers")
        time.sleep(8)

        run(
            client,
            f"docker ps --filter name={DEPLOY_ID}- --format '{{{{.Names}}}}\\t{{{{.Status}}}}'",
        )

        # 6) backend 健康检查
        print("\n[step 6] backend health check")
        run(client, f"docker exec {DEPLOY_ID}-backend curl -sf http://localhost:8000/docs -o /dev/null -w '%{{http_code}}\\n' || true")

        # 7) backend logs（最近 30 行）
        print("\n[step 7] backend tail logs")
        run(client, f"docker logs --tail 40 {DEPLOY_ID}-backend 2>&1")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
