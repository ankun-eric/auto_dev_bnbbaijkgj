"""部署支付配置 Bug 修复到远程服务器（增量上传 + docker compose）。

步骤：
1. SFTP 上传修改的后端文件 + admin-web 文件 + docker-compose.yml + 测试文件
2. docker compose down + up -d --build backend admin-web（强制重建）
3. 等待 backend 启动并 healthcheck
4. 容器内执行 pytest test_payment_config_bugfix.py + test_payment_config_v1.py
5. 通过 nginx 网关测试 /api/admin/payment-channels（401 表示路由可达）
6. 检查后端日志中支付配置启动自检消息
"""
import os
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DID}"
LOCAL_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 增量上传清单（本地相对路径）
FILES_TO_UPLOAD = [
    "backend/app/api/payment_config.py",
    "backend/app/schemas/payment_config.py",
    "backend/app/services/schema_sync.py",
    "backend/app/main.py",
    "backend/tests/test_payment_config_bugfix.py",
    "admin-web/src/app/(admin)/payment-config/page.tsx",
    "docker-compose.yml",
    ".env.example",
]


def run(client, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}")
    return out, err


def upload_file(sftp, local, remote):
    print(f"  upload: {local} -> {remote}")
    # 确保远程目录存在
    remote_dir = "/".join(remote.split("/")[:-1])
    try:
        sftp.stat(remote_dir)
    except IOError:
        # mkdir -p
        parts = remote_dir.split("/")
        for i in range(2, len(parts) + 1):
            d = "/".join(parts[:i])
            try:
                sftp.stat(d)
            except IOError:
                sftp.mkdir(d)
    sftp.put(local, remote)


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = client.open_sftp()
    try:
        # 1) 上传文件
        for rel in FILES_TO_UPLOAD:
            local = os.path.join(LOCAL_BASE, rel.replace("/", os.sep))
            remote = f"{REMOTE_BASE}/{rel}"
            if not os.path.isfile(local):
                print(f"[skip] local file missing: {local}")
                continue
            upload_file(sftp, local, remote)

        # 2) 给后端容器 docker cp 一份关键 .py（避免 build 慢；schema_sync 必须重启 backend）
        # 直接 build + recreate 更稳：env 改了必须重建
        run(client, f"cd {REMOTE_BASE} && docker compose up -d --build backend admin-web", timeout=900)

        # 3) 等待容器健康
        time.sleep(10)
        for i in range(15):
            out, _ = run(client, f"docker ps --format '{{{{.Names}}}} {{{{.Status}}}}' | grep {DID}-backend")
            if "Up" in out:
                break
            time.sleep(5)

        # 等数据库迁移完
        time.sleep(8)

        # 4) 容器内跑 pytest
        run(client, (
            f"docker exec -e PYTEST_CURRENT_TEST=1 {DID}-backend "
            f"python -m pytest tests/test_payment_config_bugfix.py tests/test_payment_config_v1.py -q"
        ), timeout=300)

        # 5) 路由 + 网关验证
        run(client, f"curl -s -o /dev/null -w 'gateway api %{{http_code}}\\n' "
                    f"https://newbb.test.bangbangvip.com/autodev/{DID}/api/admin/payment-channels")
        run(client, f"curl -s -o /dev/null -w 'gateway admin %{{http_code}}\\n' "
                    f"https://newbb.test.bangbangvip.com/autodev/{DID}/admin/")
        run(client, f"curl -s -o /dev/null -w 'gateway docs %{{http_code}}\\n' "
                    f"https://newbb.test.bangbangvip.com/autodev/{DID}/api/docs")

        # 6) 检查启动自检
        run(client, f"docker logs --tail 200 {DID}-backend 2>&1 | grep -i '\\[支付配置\\]\\|payment_config' | tail -10")

        # 7) 验证 DB 中时间戳已被回补
        run(client, f"""docker exec {DID}-backend python -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def main():
    eng = create_async_engine(os.environ['DATABASE_URL'])
    async with eng.begin() as conn:
        rows = (await conn.execute(text('SELECT channel_code, created_at, updated_at FROM payment_channels'))).fetchall()
        for r in rows:
            print(repr(dict(r._mapping)))
asyncio.run(main())
" """)

        # 8) 用真实 admin 登录后访问 list 接口
        run(client, f"docker exec {DID}-backend python -c \"\nimport asyncio, json\nimport httpx\nasync def main():\n    base='http://localhost:8000'\n    async with httpx.AsyncClient(base_url=base) as c:\n        # 找一个 admin 账号；如失败则跳过\n        r = await c.post('/api/admin/login', json={{'phone':'13800000088','password':'admin123'}})\n        print('login', r.status_code, r.text[:200])\n        if r.status_code == 200:\n            t = r.json().get('token') or r.json().get('access_token')\n            r2 = await c.get('/api/admin/payment-channels', headers={{'Authorization':'Bearer '+t}})\n            print('list', r2.status_code, r2.text[:300])\nasyncio.run(main())\n\"")
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
