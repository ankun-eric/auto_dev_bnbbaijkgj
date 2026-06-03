"""[BUGFIX HS-CALLBACK-DATATYPE 2026-05-29]
将后端 home_safety_v1.py + schema_sync.py + 新测试用例 同步到远程服务器并重启后端容器，
然后重建管理后台前端容器以使前端列变更生效。
"""
import os
import sys
import time
import paramiko
from scp import SCPClient

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
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    print(f"(rc={rc})")
    return rc, out, err


def upload(c, local, remote):
    with SCPClient(c.get_transport()) as scp:
        scp.put(local, remote)


def main():
    c = conn()
    print("=== 1. 查看远程项目目录 ===")
    run(c, f"ls /home/ubuntu/{DEPLOY_ID}/ | head -50")
    run(c, f"docker ps --format '{{{{.Names}}}}' | grep {DEPLOY_ID}")

    project_root = f"/home/ubuntu/{DEPLOY_ID}"

    print("\n=== 2. 上传修改后的后端文件 ===")
    upload(c, "backend/app/api/home_safety_v1.py", f"{project_root}/backend/app/api/home_safety_v1.py")
    upload(c, "backend/app/services/schema_sync.py", f"{project_root}/backend/app/services/schema_sync.py")
    upload(c, "backend/tests/test_home_safety_callback_datatype_v1.py", f"{project_root}/backend/tests/test_home_safety_callback_datatype_v1.py")

    print("\n=== 3. 上传修改后的管理后台前端文件 ===")
    upload(c, "admin-web/src/app/(admin)/home-safety/page.tsx", f"{project_root}/admin-web/src/app/(admin)/home-safety/page.tsx")

    print("\n=== 4. 重启后端容器 ===")
    run(c, f"docker exec {DEPLOY_ID}-backend python -c 'import ast,sys; ast.parse(open(\"/app/app/api/home_safety_v1.py\").read())' 2>&1 || true")
    # 把文件复制进容器
    run(c, f"docker cp {project_root}/backend/app/api/home_safety_v1.py {DEPLOY_ID}-backend:/app/app/api/home_safety_v1.py")
    run(c, f"docker cp {project_root}/backend/app/services/schema_sync.py {DEPLOY_ID}-backend:/app/app/services/schema_sync.py")
    run(c, f"docker cp {project_root}/backend/tests/test_home_safety_callback_datatype_v1.py {DEPLOY_ID}-backend:/app/tests/test_home_safety_callback_datatype_v1.py")
    run(c, f"docker restart {DEPLOY_ID}-backend")
    # 等就绪
    time.sleep(8)
    run(c, f"docker logs --tail 40 {DEPLOY_ID}-backend 2>&1 | tail -50")

    print("\n=== 5. 触发 schema_sync 通过健康检查 ===")
    base_url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    rc, out, _ = run(c, f"curl -sk -o /dev/null -w '%{{http_code}}' '{base_url}/api/health' || echo curl_fail")
    print(f"health rc={rc} body={out}")

    print("\n=== 6. 重建管理后台前端容器 ===")
    # 检查 admin-web 容器命名
    run(c, f"docker ps --format '{{{{.Names}}}}' | grep -i admin")


if __name__ == "__main__":
    main()
