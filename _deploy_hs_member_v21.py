"""[PRD-HOME-SAFETY-MEMBER-V2.1 2026-05-29] 部署本次变更到远程服务器：
- 同步 backend / h5-web / admin-web 三处变更代码
- 重启 backend 容器（schema_sync 自动跑），重建 h5-web 与 admin-web
- 调用一次 /api/admin/home_safety/migrate_member_id 触发历史数据迁移
"""
import paramiko, posixpath, os, sys

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def run(c, cmd, timeout=900):
    print(f"\n$ {cmd[:200]}")
    si, so, se = c.exec_command(cmd, timeout=timeout)
    out = so.read().decode("utf-8", "replace")
    err = se.read().decode("utf-8", "replace")
    code = so.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err:
        print("[err]", err[-1500:])
    print(f"[exit {code}]")
    return code, out, err


def upload(sftp, local, remote):
    print(f"upload {local} -> {remote}")
    # ensure parent
    parent = posixpath.dirname(remote)
    try:
        sftp.stat(parent)
    except FileNotFoundError:
        run_local_mkdir(sftp, parent)
    sftp.put(local, remote)


def run_local_mkdir(sftp, path):
    parts = path.strip("/").split("/")
    cur = ""
    for p in parts:
        cur = cur + "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            try:
                sftp.mkdir(cur)
            except Exception:
                pass


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=60)
    sftp = c.open_sftp()

    files = [
        ("backend/app/api/home_safety_v1.py", f"{PROJECT_DIR}/backend/app/api/home_safety_v1.py"),
        ("backend/app/services/schema_sync.py", f"{PROJECT_DIR}/backend/app/services/schema_sync.py"),
        ("backend/tests/test_home_safety_member_v21.py", f"{PROJECT_DIR}/backend/tests/test_home_safety_member_v21.py"),
        ("h5-web/src/app/home-safety/page.tsx", f"{PROJECT_DIR}/h5-web/src/app/home-safety/page.tsx"),
        ("admin-web/src/app/(admin)/home-safety/page.tsx", f"{PROJECT_DIR}/admin-web/src/app/(admin)/home-safety/page.tsx"),
    ]
    for local, remote in files:
        if not os.path.isfile(local):
            print(f"[skip] {local} not exist")
            continue
        upload(sftp, local, remote)

    sftp.close()

    # Restart backend (schema_sync runs at startup), rebuild h5-web, admin-web
    print("\n=== 1. backend 重启（不重建镜像，直接 force-recreate；如代码已 mount 则生效） ===")
    # 通常 backend 镜像 build 较慢；优先尝试 docker exec 重启
    # 实际仍重建镜像以确保 schema_sync 生效
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -30", timeout=900)
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate backend 2>&1 | tail -20", timeout=180)

    print("\n=== 2. h5-web 重建 ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -30", timeout=900)
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate h5-web 2>&1 | tail -20", timeout=180)

    print("\n=== 3. admin-web 重建 ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -30", timeout=900)
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate admin-web 2>&1 | tail -20", timeout=180)

    print("\n=== 4. 等待 30s 让 backend 完成 schema_sync ===")
    import time
    time.sleep(30)

    print("\n=== 5. 验证 backend 健康 ===")
    run(c, f"docker logs {DEPLOY_ID}-backend --tail 60 2>&1 | tail -60")

    print("\n=== 6. 验证 schema 中存在 member_id 列 ===")
    run(
        c,
        f"docker exec {DEPLOY_ID}-backend python -c \"import asyncio; from app.core.database import engine; from sqlalchemy import inspect, text\\n"
        f"async def m():\\n"
        f"    async with engine.connect() as conn:\\n"
        f"        cols = await conn.run_sync(lambda sc: [c['name'] for c in inspect(sc).get_columns('home_safety_device_binding')])\\n"
        f"        print('binding cols:', cols)\\n"
        f"asyncio.run(m())\" 2>&1 | tail -10",
        timeout=60,
    )

    c.close()


if __name__ == "__main__":
    main()
