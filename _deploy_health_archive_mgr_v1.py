"""[PRD-HEALTH-ARCHIVE-MGR-V1 2026-05-29] 健康档案管理优化（命名升级）部署脚本

涉及文件：
- backend/app/api/member_center_v2.py     → docker cp + restart（benefits_cards label/unit 改名）
- backend/app/models/membership_plan.py   → docker cp + restart（comment 注释更新）
- backend/app/schemas/membership.py       → docker cp + restart（注释更新）
- backend/tests/test_health_archive_mgr_v1_20260529.py → docker cp（新增测试）
- h5-web/src/app/health-profile/page.tsx          → rebuild
- h5-web/src/app/health-profile/i-guard/page.tsx  → rebuild
- h5-web/src/app/health-profile/v13/page.tsx      → rebuild
- h5-web/src/app/member-center/page.tsx           → rebuild
- h5-web/src/app/member-center/components/BenefitsCompareTable.tsx → rebuild
- miniprogram/pages/health-profile/index.wxml     → 源码同步（用户在小程序开发者工具中重新打包）
- miniprogram/pages/health-profile/index.js       → 源码同步（注释）
- admin-web/src/app/(admin)/membership/plans/page.tsx → rebuild admin-web
- admin-web/src/app/(admin)/membership/free-quota/page.tsx → rebuild admin-web
- admin-web/src/app/(admin)/users/page.tsx → rebuild admin-web
- admin-web/src/app/(admin)/family-management/page.tsx → rebuild admin-web

策略：
1) backend 走 docker cp 热更 + docker restart
2) h5-web / admin-web 走 docker compose build + up -d
3) 部署后跑 pytest 做 health_archive_mgr_v1 用例验证
4) HTTPS smoke 测试主要页面 200
"""
from __future__ import annotations
import os
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

# (local_path, remote_host_path, docker_cp_inside_path_or_None, container_keyword_or_None)
LOCAL_FILES = [
    ("backend/app/api/member_center_v2.py",
     f"{PROJECT_DIR}/backend/app/api/member_center_v2.py",
     "/app/app/api/member_center_v2.py",
     "backend"),
    ("backend/app/models/membership_plan.py",
     f"{PROJECT_DIR}/backend/app/models/membership_plan.py",
     "/app/app/models/membership_plan.py",
     "backend"),
    ("backend/app/schemas/membership.py",
     f"{PROJECT_DIR}/backend/app/schemas/membership.py",
     "/app/app/schemas/membership.py",
     "backend"),
    ("backend/tests/test_health_archive_mgr_v1_20260529.py",
     f"{PROJECT_DIR}/backend/tests/test_health_archive_mgr_v1_20260529.py",
     "/app/tests/test_health_archive_mgr_v1_20260529.py",
     "backend"),
    # H5 - 仅源码同步，rebuild 在主机执行
    ("h5-web/src/app/health-profile/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/health-profile/page.tsx", None, None),
    ("h5-web/src/app/health-profile/i-guard/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/health-profile/i-guard/page.tsx", None, None),
    ("h5-web/src/app/health-profile/v13/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/health-profile/v13/page.tsx", None, None),
    ("h5-web/src/app/member-center/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/member-center/page.tsx", None, None),
    ("h5-web/src/app/member-center/components/BenefitsCompareTable.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/member-center/components/BenefitsCompareTable.tsx", None, None),
    # admin-web - 仅源码同步
    ("admin-web/src/app/(admin)/membership/plans/page.tsx",
     f"{PROJECT_DIR}/admin-web/src/app/(admin)/membership/plans/page.tsx", None, None),
    ("admin-web/src/app/(admin)/membership/free-quota/page.tsx",
     f"{PROJECT_DIR}/admin-web/src/app/(admin)/membership/free-quota/page.tsx", None, None),
    ("admin-web/src/app/(admin)/users/page.tsx",
     f"{PROJECT_DIR}/admin-web/src/app/(admin)/users/page.tsx", None, None),
    ("admin-web/src/app/(admin)/family-management/page.tsx",
     f"{PROJECT_DIR}/admin-web/src/app/(admin)/family-management/page.tsx", None, None),
    # 小程序源码（用户自行通过开发者工具重新预览）
    ("miniprogram/pages/health-profile/index.wxml",
     f"{PROJECT_DIR}/miniprogram/pages/health-profile/index.wxml", None, None),
    ("miniprogram/pages/health-profile/index.js",
     f"{PROJECT_DIR}/miniprogram/pages/health-profile/index.js", None, None),
]


def ssh_connect():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=PORT, username=USER, password=PASSWORD,
                timeout=60, banner_timeout=60, auth_timeout=60,
                look_for_keys=False, allow_agent=False)
    cli.get_transport().set_keepalive(30)
    return cli


def sq(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


def run(cli, cmd, *, timeout=300, sudo=False, check=True, quiet=False):
    full = cmd
    if sudo:
        full = f"echo {sq(PASSWORD)} | sudo -S bash -lc {sq(cmd)}"
    if not quiet:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}")
    stdin, stdout, stderr = cli.exec_command(full, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    rc = stdout.channel.recv_exit_status()
    if not quiet:
        if out.strip():
            print(out[-3500:])
        if err.strip():
            print(f"[stderr] {err[-1500:]}")
        print(f"[rc={rc}]")
    if check and rc != 0:
        raise RuntimeError(f"cmd failed rc={rc}: {cmd}")
    return rc, out, err


def find_container(cli, kw):
    rc, out, _ = run(cli, "docker ps --format '{{.Names}}'", check=False, quiet=True)
    names = [n.strip() for n in out.splitlines() if n.strip()]
    for n in names:
        if kw in n.lower() and DEPLOY_ID in n:
            return n
    return None


def upload_file(sftp, local, remote):
    print(f"  upload {local} → {remote}")
    # ensure remote dir
    remote_dir = remote.rsplit("/", 1)[0]
    parts = remote_dir.split("/")
    cur = ""
    for p in parts:
        if not p:
            cur = "/"
            continue
        cur = cur.rstrip("/") + "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass
    sftp.put(local, remote)


def main():
    print(f"[deploy] connecting to {USER}@{HOST} ...")
    cli = ssh_connect()
    sftp = cli.open_sftp()
    try:
        # 1) 上传源码到主机
        for local, remote_host, _docker_path, _kw in LOCAL_FILES:
            local_abs = os.path.abspath(local)
            if not os.path.exists(local_abs):
                raise FileNotFoundError(local_abs)
            upload_file(sftp, local_abs, remote_host)

        # 2) backend 文件 docker cp 进 backend 容器
        be_name = find_container(cli, "backend")
        if not be_name:
            raise RuntimeError("找不到 backend 容器")
        print(f"[deploy] backend container: {be_name}")
        for _local, remote_host, docker_path, kw in LOCAL_FILES:
            if kw == "backend" and docker_path:
                run(cli, f"docker cp {remote_host} {be_name}:{docker_path}", sudo=True)
        run(cli, f"docker restart {be_name}", sudo=True)

        # 等待 backend 起来
        print("[deploy] waiting backend ready ...")
        for i in range(30):
            rc, out, _ = run(
                cli,
                f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost/autodev/{DEPLOY_ID}/api/health",
                check=False, quiet=True
            )
            if "200" in out:
                print(f"[deploy] backend ready after {i+1}s")
                break
            time.sleep(1)
        else:
            print("[deploy] backend health 超时，继续后续步骤")

        # 3) 跑 pytest（新增用例）
        print("\n[deploy] === pytest health_archive_mgr_v1 ===")
        rc, out, err = run(
            cli,
            f"docker exec {be_name} python -m pytest tests/test_health_archive_mgr_v1_20260529.py -v -x --tb=short",
            sudo=True, check=False, timeout=300
        )
        if rc != 0:
            print("[deploy] !! pytest 失败，将在最后退出")
            global PYTEST_RC
            PYTEST_RC = rc

        # 4) h5-web rebuild
        print("\n[deploy] === rebuild h5-web ===")
        run(cli, f"cd {PROJECT_DIR} && docker compose build h5-web && docker compose up -d h5-web",
            sudo=True, timeout=600)

        # 5) admin-web rebuild
        print("\n[deploy] === rebuild admin-web ===")
        run(cli, f"cd {PROJECT_DIR} && docker compose build admin-web && docker compose up -d admin-web",
            sudo=True, timeout=600)

        # 6) backend rebuild 期间可能被重启，重新 docker cp 一遍 backend 文件
        be_name2 = find_container(cli, "backend")
        if be_name2:
            print(f"[deploy] re-cp backend after compose: {be_name2}")
            for _local, remote_host, docker_path, kw in LOCAL_FILES:
                if kw == "backend" and docker_path:
                    run(cli, f"docker cp {remote_host} {be_name2}:{docker_path}", sudo=True, check=False)
            run(cli, f"docker restart {be_name2}", sudo=True, check=False)

        # 7) smoke 测试
        print("\n[deploy] === smoke ===")
        base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
        for path in [
            "/api/health",
            "/health-profile/",
            "/health-profile/i-guard/",
            "/member-center/",
        ]:
            rc, out, _ = run(
                cli,
                f"curl -sk -o /dev/null -w '%{{http_code}}' {base}{path}",
                check=False, quiet=True
            )
            print(f"  GET {path} → {out.strip()}")

        # 8) 验证 /api/member/center 字段对齐（不带 token 返回 401 即可证明路由仍工作）
        rc, out, _ = run(
            cli,
            f"curl -sk -o /dev/null -w '%{{http_code}}' {base}/api/member/center",
            check=False, quiet=True
        )
        print(f"  GET /api/member/center (no auth) → {out.strip()} (期望 401)")

    finally:
        try:
            sftp.close()
        except Exception:
            pass
        cli.close()
        print("[deploy] done.")


PYTEST_RC = 0

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[deploy] FAIL: {e}")
        sys.exit(2)
    if PYTEST_RC != 0:
        print(f"[deploy] WARN pytest rc={PYTEST_RC}")
        sys.exit(PYTEST_RC)
    sys.exit(0)
