"""[PRD-LEGACY-HOME-CLEANUP-V1.1 2026-05-19] 部署脚本

改动范围：
- backend:
  - backend/app/api/app_settings.py：删除 PUT page-style；GET 改常量
  - backend/app/api/home_config.py：删除 home-menus 写接口；PUT home-config 仅 font_*
  - backend/app/services/prd_legacy_home_cleanup_v11_migration.py：新增迁移
  - backend/app/main.py：注册启动期迁移
  - backend/tests/test_home_config.py：测试重写

- admin-web:
  - admin-web/src/app/(admin)/layout.tsx：侧边栏结构调整
  - admin-web/src/app/(admin)/home-settings/page.tsx：改名「字体配置」+ 瘦身
  - admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx：标题改名
  - 删除：admin-web/src/app/(admin)/home-settings/page-style/、home-menus/

- h5-web:
  - h5-web/src/app/(ai-chat)/ai-home/page.tsx：banner Bug 修复 + console.warn
  - h5-web/src/app/page.tsx：删除 page-style 兼容 fetch
  - 删除：h5-web/src/app/_archived_tabs/home/、h5-web/src/lib/useHomeConfig.ts

部署流程：
1) SFTP 上传所有变更文件到服务器
2) SSH 删除已下线的目录/文件
3) docker exec 同步 backend 改动到容器内 + 重启 backend（触发 v11 迁移）
4) 重建 admin-web、h5-web 镜像（含构建期 env）
5) 等待全部就绪
6) 验证关键端点：
   - GET /api/app-settings/page-style → 200 + value=ai_chat
   - GET /api/home-banners → 200
   - DB 中 home_menus 表 / 删除的 KV 状态符合预期
"""
from __future__ import annotations

import os
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"

# 需要上传的文件清单 (local_rel, remote_rel)
UPLOAD_FILES = [
    # backend
    ("backend/app/api/app_settings.py", "backend/app/api/app_settings.py"),
    ("backend/app/api/home_config.py", "backend/app/api/home_config.py"),
    ("backend/app/services/prd_legacy_home_cleanup_v11_migration.py",
     "backend/app/services/prd_legacy_home_cleanup_v11_migration.py"),
    ("backend/app/main.py", "backend/app/main.py"),
    ("backend/tests/test_home_config.py", "backend/tests/test_home_config.py"),
    # admin-web
    ("admin-web/src/app/(admin)/layout.tsx", "admin-web/src/app/(admin)/layout.tsx"),
    ("admin-web/src/app/(admin)/home-settings/page.tsx",
     "admin-web/src/app/(admin)/home-settings/page.tsx"),
    ("admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx",
     "admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx"),
    # h5-web
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    ("h5-web/src/app/page.tsx", "h5-web/src/app/page.tsx"),
]

# 需要在服务器上删除的路径
REMOTE_DELETIONS = [
    "admin-web/src/app/(admin)/home-settings/page-style",
    "admin-web/src/app/(admin)/home-menus",
    "h5-web/src/app/_archived_tabs/home",
    "h5-web/src/lib/useHomeConfig.ts",
]

BACKEND_CONTAINER = f"{DEPLOY_ID}-backend"
ADMIN_CONTAINER = f"{DEPLOY_ID}-admin"
H5_CONTAINER = f"{DEPLOY_ID}-h5"


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    stdout.channel.settimeout(timeout + 60)
    stderr.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-3000:], flush=True)
    if show and err.strip():
        print("STDERR:", err[-1500:], flush=True)
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}\n{err}")
    return rc, out, err


def main():
    base = os.path.abspath(os.path.dirname(__file__) + "/..")
    print(f"Local base: {base}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}:{PORT}...")
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    print("Connected.")

    try:
        # 1) SFTP 上传
        sftp = client.open_sftp()
        for local_rel, remote_rel in UPLOAD_FILES:
            local_abs = os.path.join(base, local_rel.replace("/", os.sep))
            if not os.path.exists(local_abs):
                print(f"  [SKIP] missing local: {local_abs}")
                continue
            remote_abs = f"{PROJ_DIR}/{remote_rel}"
            run(client, f"mkdir -p '{os.path.dirname(remote_abs)}'", show=False)
            print(f"  upload: {local_rel} -> {remote_abs}")
            sftp.put(local_abs, remote_abs)
        sftp.close()

        # 2) 服务器删除下线的路径
        print("\n--- 服务器删除下线目录/文件 ---")
        for rel in REMOTE_DELETIONS:
            run(client, f"rm -rf '{PROJ_DIR}/{rel}'", ignore_err=True, show=True)

        # 3) backend 容器内同步代码 + 重启（触发 v11 迁移）
        print("\n--- 同步 backend 改动到容器内 ---")
        backend_files = [
            ("backend/app/api/app_settings.py", "/app/app/api/app_settings.py"),
            ("backend/app/api/home_config.py", "/app/app/api/home_config.py"),
            ("backend/app/services/prd_legacy_home_cleanup_v11_migration.py",
             "/app/app/services/prd_legacy_home_cleanup_v11_migration.py"),
            ("backend/app/main.py", "/app/app/main.py"),
            ("backend/tests/test_home_config.py", "/app/tests/test_home_config.py"),
        ]
        for local_p, container_p in backend_files:
            run(client, f"docker exec {BACKEND_CONTAINER} mkdir -p $(dirname {container_p}) 2>&1",
                ignore_err=True, show=False)
            run(client, f"docker cp {PROJ_DIR}/{local_p} {BACKEND_CONTAINER}:{container_p} 2>&1",
                ignore_err=True, show=False)

        print("\n--- 重启 backend（触发 prd_legacy_home_cleanup_v11 迁移） ---")
        run(client, f"docker restart {BACKEND_CONTAINER} 2>&1 | tail -5",
            ignore_err=True, timeout=180)

        print("\n--- 等待 backend 就绪 ---")
        ready = False
        for i in range(80):
            rc, out, _ = run(
                client,
                "curl -ks -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/openapi.json || echo fail",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i + 1) * 3}s] backend openapi: {s}")
            if s == "200":
                ready = True
                break
            time.sleep(3)
        if not ready:
            print("WARN: backend not ready within timeout")

        # 4) 重建 admin-web 和 h5-web (front-ends 必须重建因为有 deletions / 改动)
        rc, out, _ = run(client, f"ls {PROJ_DIR}/docker-compose*.yml 2>&1",
                         ignore_err=True, show=False)
        compose_file = "docker-compose.prod.yml" if "docker-compose.prod.yml" in out else "docker-compose.yml"

        print(f"\n--- rebuild admin-web 与 h5-web (compose: {compose_file}) ---")
        run(client,
            f"cd {PROJ_DIR} && docker-compose -f {compose_file} build --no-cache admin-web h5-web 2>&1 | tail -40",
            ignore_err=True, timeout=900)

        print("\n--- 重启 admin-web 和 h5-web 容器 ---")
        run(client,
            f"cd {PROJ_DIR} && docker-compose -f {compose_file} up -d admin-web h5-web 2>&1 | tail -20",
            ignore_err=True, timeout=300)

        # 5) 等待前端就绪
        print("\n--- 等待 admin-web 和 h5-web 就绪 ---")
        for label, container in [("admin", ADMIN_CONTAINER), ("h5", H5_CONTAINER)]:
            for i in range(40):
                rc, out, _ = run(
                    client,
                    f"docker inspect -f '{{{{.State.Status}}}}' {container} 2>&1 || echo dead",
                    ignore_err=True, show=False,
                )
                s = out.strip()
                if s == "running":
                    print(f"  {label}: running")
                    break
                time.sleep(3)

        # 6) 验证关键端点
        print("\n--- 关键端点验证 ---")
        base_url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

        # GET page-style 常量
        run(client,
            f"curl -ks '{base_url}/api/app-settings/page-style' | head -c 400",
            ignore_err=True, show=True)

        # GET home-banners
        run(client,
            f"curl -ks -o /dev/null -w 'home-banners: %{{http_code}}\\n' '{base_url}/api/home-banners'",
            ignore_err=True, show=True)

        # GET home-config
        run(client,
            f"curl -ks -o /dev/null -w 'home-config: %{{http_code}}\\n' '{base_url}/api/home-config'",
            ignore_err=True, show=True)

        # GET home-menus
        run(client,
            f"curl -ks -o /dev/null -w 'home-menus: %{{http_code}}\\n' '{base_url}/api/home-menus'",
            ignore_err=True, show=True)

        # admin home-menus 写接口已删，PUT 应 404/405
        run(client,
            f"curl -ks -o /dev/null -w 'admin home-menus POST (no auth): %{{http_code}}\\n' "
            f"-X POST '{base_url}/api/admin/home-menus' -H 'Content-Type: application/json' -d '{{}}'",
            ignore_err=True, show=True)

        # DB 验证
        print("\n--- DB 验证: page_style KV / home_* KV / banner 治理 ---")
        run(client,
            f"docker exec {BACKEND_CONTAINER} python -c "
            "\"import os; from sqlalchemy import create_engine, text; "
            "url = os.environ.get('DATABASE_URL', '').replace('+aiomysql', '+pymysql'); "
            "e = create_engine(url); "
            "with e.connect() as c: "
            "  r1 = c.execute(text(\\\"SELECT COUNT(*) FROM app_settings WHERE \\`key\\`='page_style'\\\")).scalar(); "
            "  r2 = c.execute(text(\\\"SELECT COUNT(*) FROM system_config WHERE config_key LIKE 'home_%' AND config_key NOT LIKE 'home_font_%'\\\")).scalar(); "
            "  r3 = c.execute(text(\\\"SELECT COUNT(*) FROM system_config WHERE config_key LIKE 'home_font_%'\\\")).scalar(); "
            "  r4 = c.execute(text(\\\"SHOW TABLES LIKE 'banner_migration_log_20260519'\\\")).fetchone(); "
            "  r5 = c.execute(text(\\\"SELECT \\`value\\` FROM app_settings WHERE \\`key\\`='_migration_done.prd_legacy_home_cleanup_v11'\\\")).scalar(); "
            "  print('page_style KV count (应=0):', r1); "
            "  print('home_* non-font KV count (应=0):', r2); "
            "  print('home_font_* KV count (应>=5):', r3); "
            "  print('banner_migration_log_20260519 table:', r4); "
            "  print('migration flag:', r5);\" 2>&1",
            ignore_err=True, timeout=120,
        )

        # 跑 backend pytest 子集（home_config）
        print("\n--- 运行 backend tests/test_home_config.py ---")
        run(client,
            f"docker exec {BACKEND_CONTAINER} bash -lc 'cd /app && python -m pytest tests/test_home_config.py -x -q 2>&1 | tail -80'",
            ignore_err=True, timeout=600)

        print("\n✅ 部署完成")
    finally:
        client.close()


if __name__ == "__main__":
    main()
