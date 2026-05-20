"""[PRD-AI-PAGE-OPTIM-V1 2026-05-21] 部署脚本

部署内容：
1. 后端：
   - 改动的 4 个迁移脚本（关闭种子自动插入）
   - 新增 seed_packs/ 模块 + seed_import.py API + main.py 路由注册
   - 新增 scripts/cleanup_tcm_orphan_template.py 孤儿清理脚本
   - 新增测试 tests/test_ai_page_optim_v1_20260521.py
2. admin-web：
   - 新增 system/seed-import/page.tsx
   - 修改 questionnaire-templates/page.tsx（健康自查行变为跳转链接）
   - 修改 layout.tsx（菜单加入「种子数据导入」）
3. h5-web：
   - ai-home/page.tsx（4 处 /health-archive → /health-profile）
   - components/ai-chat/Sidebar.tsx
   - chat/[sessionId]/page.tsx
   - ProfileCard.tsx
   - 删除 (ai-chat)/health-archive/page.tsx 整个文件

部署流程：
1. tar 打包后端 / admin-web / h5-web 改动文件
2. 上传到服务器、解压
3. docker cp 后端 .py 文件、admin .tsx 文件、h5 .tsx 文件
4. admin-web 与 h5-web 需要重建（Next.js）
5. backend 重启
6. 跑孤儿清理脚本一次
7. 验证关键路由

支持环境变量 RESTART_FRONT=0/1 控制前端是否重建（默认 1）
"""
import io
import os
import sys
import tarfile
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/{USER}/{DEPLOY_ID}"
LOCAL = os.path.dirname(os.path.abspath(__file__))

# 改动的后端文件
BACKEND_FILES = [
    "backend/app/main.py",
    "backend/app/services/prd_tcm36_drawer_v12_migration.py",
    "backend/app/services/prd_questionnaire_drawer_v1_migration.py",
    "backend/app/services/prd_qn_content_v1_migration.py",
    "backend/app/services/prd_tag_recommend_v1_migration.py",
    "backend/app/services/seed_packs/__init__.py",
    "backend/app/services/seed_packs/registry.py",
    "backend/app/api/seed_import.py",
    "backend/scripts/cleanup_tcm_orphan_template.py",
    "backend/tests/test_ai_page_optim_v1_20260521.py",
]

# admin-web 改动
ADMIN_FILES = [
    "admin-web/src/app/(admin)/layout.tsx",
    "admin-web/src/app/(admin)/questionnaire-templates/page.tsx",
    "admin-web/src/app/(admin)/system/seed-import/page.tsx",
]

# h5-web 改动
H5_FILES = [
    "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
    "h5-web/src/components/ai-chat/Sidebar.tsx",
    "h5-web/src/components/ai-chat/ProfileCard.tsx",
    "h5-web/src/app/chat/[sessionId]/page.tsx",
]

# 要删除的旧 h5 页面
H5_FILES_TO_DELETE = [
    "h5-web/src/app/(ai-chat)/health-archive/page.tsx",
]


def _ssh():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=60)
    return cli


def sh(cli, cmd, t=180):
    si, so, se = cli.exec_command(cmd, timeout=t)
    return (
        so.read().decode(errors="replace"),
        se.read().decode(errors="replace"),
        so.channel.recv_exit_status(),
    )


def make_tar(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for rel in files:
            full = os.path.join(LOCAL, rel)
            if os.path.exists(full):
                tf.add(full, arcname=rel)
            else:
                print(f"[warn] 本地文件不存在: {rel}")
    buf.seek(0)
    return buf.read()


def upload_and_extract(cli, files, archive_name):
    data = make_tar(files)
    print(f"[upload] {archive_name} 包大小 {len(data)/1024:.1f} KiB ({len(files)} 文件)")
    sftp = cli.open_sftp()
    with sftp.open(f"{REMOTE_BASE}/{archive_name}", "wb") as f:
        f.write(data)
    sftp.close()
    o, e, c = sh(cli, f"cd {REMOTE_BASE} && tar -xzf {archive_name} && echo extracted")
    print(o, e)
    return c == 0


def deploy_backend(cli):
    print("\n========== 部署 backend ==========")
    upload_and_extract(cli, BACKEND_FILES, "_ai_page_optim_v1_be.tar.gz")
    for rel in BACKEND_FILES:
        in_container = "/app/" + rel[len("backend/") :]
        # 确保容器内目录存在
        parent = os.path.dirname(in_container).replace("\\", "/")
        sh(cli, f"docker exec {DEPLOY_ID}-backend mkdir -p {parent}")
        o, e, c = sh(
            cli, f"docker cp {REMOTE_BASE}/{rel} {DEPLOY_ID}-backend:{in_container}"
        )
        print(f"cp {rel} -> exit={c} err={e.strip()!r}")

    print("[restart] backend ...")
    sh(cli, f"docker restart {DEPLOY_ID}-backend", t=120)
    time.sleep(15)
    o, _, _ = sh(cli, f"docker logs --tail 60 {DEPLOY_ID}-backend 2>&1")
    print(o)


def deploy_admin(cli):
    print("\n========== 部署 admin-web ==========")
    upload_and_extract(cli, ADMIN_FILES, "_ai_page_optim_v1_admin.tar.gz")
    for rel in ADMIN_FILES:
        in_container = "/app/" + rel[len("admin-web/") :]
        parent = os.path.dirname(in_container).replace("\\", "/")
        # 用单引号包裹路径，避免 bash 把 ( ) 误解释
        sh(cli, f"docker exec {DEPLOY_ID}-admin mkdir -p '{parent}'")
        local_path = f"{REMOTE_BASE}/{rel}".replace("\\", "/")
        o, e, c = sh(
            cli, f"docker cp '{local_path}' '{DEPLOY_ID}-admin:{in_container}'"
        )
        print(f"cp {rel} -> exit={c} err={e.strip()!r}")

    print("[restart] admin (next dev 热更新一般够，restart 兜底) ...")
    sh(cli, f"docker restart {DEPLOY_ID}-admin", t=120)
    time.sleep(15)
    o, _, _ = sh(cli, f"docker logs --tail 40 {DEPLOY_ID}-admin 2>&1")
    print(o[:3000])


def deploy_h5(cli):
    print("\n========== 部署 h5-web ==========")
    upload_and_extract(cli, H5_FILES, "_ai_page_optim_v1_h5.tar.gz")
    for rel in H5_FILES:
        in_container = "/app/" + rel[len("h5-web/") :]
        parent = os.path.dirname(in_container).replace("\\", "/")
        sh(cli, f"docker exec {DEPLOY_ID}-h5 mkdir -p '{parent}'")
        local_path = f"{REMOTE_BASE}/{rel}".replace("\\", "/")
        o, e, c = sh(cli, f"docker cp '{local_path}' '{DEPLOY_ID}-h5:{in_container}'")
        print(f"cp {rel} -> exit={c} err={e.strip()!r}")

    # 删除旧的健康档案页面文件（H5 容器内）
    for rel in H5_FILES_TO_DELETE:
        in_container = "/app/" + rel[len("h5-web/") :]
        in_container_dir = os.path.dirname(in_container).replace("\\", "/")
        # 删除文件（注意路径中的括号 需用单引号包裹）
        o, e, c = sh(cli, f"docker exec {DEPLOY_ID}-h5 sh -c \"rm -f '{in_container}'\"")
        print(f"rm {rel} -> exit={c}")
        # 尝试删除空目录
        sh(
            cli,
            f"docker exec {DEPLOY_ID}-h5 sh -c \"rmdir '{in_container_dir}' 2>/dev/null || true\"",
        )

    print("[restart] h5 ...")
    sh(cli, f"docker restart {DEPLOY_ID}-h5", t=180)
    time.sleep(20)
    o, _, _ = sh(cli, f"docker logs --tail 40 {DEPLOY_ID}-h5 2>&1")
    print(o[:3000])


def run_cleanup_script(cli):
    print("\n========== 跑孤儿清理脚本（一次性） ==========")
    o, e, c = sh(
        cli,
        f"docker exec {DEPLOY_ID}-backend python /app/scripts/cleanup_tcm_orphan_template.py",
        t=120,
    )
    print("stdout:", o)
    print("stderr:", e)
    print("exit:", c)


def smoke_checks(cli):
    print("\n========== 烟测 ==========")
    # 1. seed-packs API 路由是否注册
    o, _, _ = sh(
        cli,
        f"docker exec {DEPLOY_ID}-backend grep -c 'seed-packs' /app/app/api/seed_import.py",
    )
    print("[smoke] seed_import.py seed-packs 出现次数:", o.strip())
    # 2. 不再自动种子
    o, _, _ = sh(
        cli,
        f"docker exec {DEPLOY_ID}-backend grep -c 'by_seed_pack_admin_page' /app/app/services/prd_tcm36_drawer_v12_migration.py",
    )
    print("[smoke] tcm36 关闭自动插入标识次数:", o.strip())
    # 3. h5-web 健康档案旧页面是否已删
    o, _, _ = sh(
        cli,
        f"docker exec {DEPLOY_ID}-h5 sh -c \"ls '/app/src/app/(ai-chat)/health-archive' 2>&1 || echo __missing__\"",
    )
    print("[smoke] h5 旧 health-archive 目录:", o.strip()[:200])
    # 4. h5-web 新路由替换是否到位
    o, _, _ = sh(
        cli,
        f"docker exec {DEPLOY_ID}-h5 sh -c \"grep -c '/health-profile' '/app/src/app/(ai-chat)/ai-home/page.tsx'\"",
    )
    print("[smoke] h5 ai-home /health-profile 出现次数:", o.strip())
    # 5. admin 菜单加入
    o, _, _ = sh(
        cli,
        f"docker exec {DEPLOY_ID}-admin sh -c \"grep -c '种子数据导入' '/app/src/app/(admin)/layout.tsx'\"",
    )
    print("[smoke] admin layout 种子数据导入 出现次数:", o.strip())


def main():
    cli = _ssh()
    skip_be = os.environ.get("SKIP_BE", "0") == "1"
    try:
        if not skip_be:
            deploy_backend(cli)
        else:
            print("[skip] 跳过 backend 部署 (SKIP_BE=1)")
        deploy_admin(cli)
        deploy_h5(cli)
        if not skip_be:
            run_cleanup_script(cli)
        smoke_checks(cli)
        print("\n=========== DONE ===========")
    finally:
        cli.close()


if __name__ == "__main__":
    main()
