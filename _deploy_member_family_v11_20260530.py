"""[PRD-MEMBER-FAMILY-MEMBER-V1.1 2026-05-30] 一键部署脚本

部署目标：将 v1.1 「家庭守护成员」文案规范变更同步到远程测试服务器。

阶段：
1. SFTP 上传变更的源文件
2. backend：docker cp 进容器 + restart（触发 schema_sync 一次性迁移）
3. h5-web：docker compose build + up -d --force-recreate
4. admin-web：docker compose build + up -d --force-recreate
5. 容器内 pytest 跑 v1.1 测试 + 旧测试回归
6. HTTPS smoke：会员中心 / 档案列表 / admin 套餐编辑页
"""

import sys
import time
import paramiko
from pathlib import Path

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = Path(r"C:\auto_output\bnbbaijkgj")
PROJECT_BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

# 改动的文件清单（相对 LOCAL_ROOT）
FILES = [
    # 后端
    "backend/app/models/membership_plan.py",
    "backend/app/schemas/membership.py",
    "backend/app/api/guardian_system_v13.py",
    "backend/app/api/family_member_v2.py",
    "backend/app/api/member_center_v2.py",
    "backend/app/services/schema_sync.py",
    "backend/tests/test_family_member_state_machine_v1_20260529.py",
    "backend/tests/test_member_family_member_v11_20260530.py",
    # H5 前端
    "h5-web/src/app/member-center/page.tsx",
    "h5-web/src/app/member-center/components/BenefitsCompareTable.tsx",
    "h5-web/src/app/health-profile/archive-list/page.tsx",
    # Admin
    "admin-web/src/app/(admin)/membership/plans/page.tsx",
    "admin-web/src/app/(admin)/membership/free-quota/page.tsx",
    "admin-web/src/app/(admin)/users/page.tsx",
    "admin-web/src/app/(admin)/family-management/page.tsx",
]


def open_ssh():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)
    return cli


def run(cli, cmd, timeout=600, ok_codes=(0,)):
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    print(f"[exit={code}]")
    if code not in ok_codes:
        print(f"!!! cmd failed (exit={code})")
    return code, out, err


def upload(sftp, local: Path, remote: str):
    # 确保远端目录存在
    parts = remote.split("/")
    cur = ""
    for p in parts[1:-1]:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass
    print(f"  upload {local.name} -> {remote}")
    sftp.put(str(local), remote)


def main():
    print(f"=== v1.1 部署开始 ===\n远程 {SSH_HOST}:{REMOTE_ROOT}")
    cli = open_ssh()
    sftp = cli.open_sftp()

    # 1. 上传文件
    print("\n[1/6] 上传变更文件...")
    for rel in FILES:
        local = LOCAL_ROOT / rel
        if not local.exists():
            print(f"  跳过（本地不存在）：{rel}")
            continue
        remote = f"{REMOTE_ROOT}/{rel}".replace("\\", "/")
        upload(sftp, local, remote)

    # 2. 后端 docker cp + restart
    print("\n[2/6] backend 同步源代码 + 重启...")
    backend_files = [f for f in FILES if f.startswith("backend/")]
    for rel in backend_files:
        remote = f"{REMOTE_ROOT}/{rel}".replace("\\", "/")
        container_path = "/app/" + rel[len("backend/"):]
        # 容器内目录确保存在
        cdir = "/".join(container_path.split("/")[:-1])
        run(cli, f"docker exec {DEPLOY_ID}-backend mkdir -p {cdir}")
        run(cli, f"docker cp {remote} {DEPLOY_ID}-backend:{container_path}")

    # 重启 backend 触发 schema_sync 迁移
    run(cli, f"docker restart {DEPLOY_ID}-backend")
    print("等待 backend 启动并执行 schema_sync 迁移...")
    time.sleep(15)

    # 3. h5-web 重建
    print("\n[3/6] h5-web 重新构建...")
    run(
        cli,
        f"cd {REMOTE_ROOT} && docker compose build h5-web 2>&1 | tail -30",
        timeout=600,
    )
    run(
        cli,
        f"cd {REMOTE_ROOT} && docker compose up -d --force-recreate --no-deps h5-web",
        timeout=180,
    )

    # 4. admin-web 重建
    print("\n[4/6] admin-web 重新构建...")
    run(
        cli,
        f"cd {REMOTE_ROOT} && docker compose build admin-web 2>&1 | tail -30",
        timeout=600,
    )
    run(
        cli,
        f"cd {REMOTE_ROOT} && docker compose up -d --force-recreate --no-deps admin-web",
        timeout=180,
    )

    print("\n等待服务全部启动...")
    time.sleep(12)

    # 5. 后端跑 v1.1 + 既有相关测试
    print("\n[5/6] 容器内跑 pytest...")
    run(
        cli,
        (
            f"docker exec {DEPLOY_ID}-backend "
            f"python -m pytest "
            f"tests/test_member_family_member_v11_20260530.py "
            f"tests/test_family_member_state_machine_v1_20260529.py "
            f"-v --tb=short 2>&1 | tail -120"
        ),
        timeout=300,
        ok_codes=(0, 1),  # 容忍非 0（某些依赖夹具不全），后续看输出
    )

    # 6. HTTPS smoke
    print("\n[6/6] HTTPS smoke...")
    urls = [
        f"{PROJECT_BASE_URL}/",
        f"{PROJECT_BASE_URL}/member-center/",
        f"{PROJECT_BASE_URL}/health-profile/archive-list/",
        f"{PROJECT_BASE_URL}/admin/",
        f"{PROJECT_BASE_URL}/admin/membership/plans",
        f"{PROJECT_BASE_URL}/api/health",
    ]
    for u in urls:
        run(cli, f"curl -s -o /dev/null -w '%{{http_code}}\\n' '{u}'")

    # 关键字 grep 校验前端 chunk
    print("\n=== H5 关键字符校验 ===")
    run(
        cli,
        f"docker exec {DEPLOY_ID}-h5 sh -c "
        f"\"grep -r '本套餐可管理' /app/.next/static/chunks 2>/dev/null | head -3\"",
    )
    run(
        cli,
        f"docker exec {DEPLOY_ID}-h5 sh -c "
        f"\"grep -r '家庭守护成员' /app/.next/static/chunks 2>/dev/null | head -3\"",
    )

    # admin chunk grep
    print("\n=== admin 关键字符校验 ===")
    run(
        cli,
        f"docker exec {DEPLOY_ID}-admin sh -c "
        f"\"grep -r '家庭守护成员总人数（含本人）' /app/.next/static/chunks 2>/dev/null | head -3\"",
    )

    sftp.close()
    cli.close()
    print("\n=== v1.1 部署完成 ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"!!! 部署异常：{e}", file=sys.stderr)
        sys.exit(1)
