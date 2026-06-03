"""[BUGFIX HOME-SAFETY-MEMBER-TAB-ALARM-REMARK 2026-05-29] 居家安全 设备备注 + 报警记录 + 公共成员 Tab 部署脚本

涉及文件：
- backend/app/api/home_safety_v1.py        → docker cp + restart
- backend/app/services/schema_sync.py      → docker cp + restart
- backend/tests/test_home_safety_remark_alarms_v1_20260529.py → docker cp（新测试）
- backend/tests/test_home_safety_*.py      → docker cp（旧测试加 remark）
- h5-web/src/components/family/FamilyMemberTabs.tsx → rebuild
- h5-web/src/app/home-safety/components/AlarmList.tsx → rebuild
- h5-web/src/app/home-safety/page.tsx       → rebuild
- admin-web/src/app/(admin)/home-safety/page.tsx → rebuild

策略：
1) backend 走 docker cp 热更 + docker restart
2) h5-web / admin-web 走 docker compose build + up -d
3) 部署后跑 pytest 验证（新+回归用例）
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
    # ── backend ──
    ("backend/app/api/home_safety_v1.py",
     f"{PROJECT_DIR}/backend/app/api/home_safety_v1.py",
     "/app/app/api/home_safety_v1.py",
     "backend"),
    ("backend/app/services/schema_sync.py",
     f"{PROJECT_DIR}/backend/app/services/schema_sync.py",
     "/app/app/services/schema_sync.py",
     "backend"),
    # ── 新测试 ──
    ("backend/tests/test_home_safety_remark_alarms_v1_20260529.py",
     f"{PROJECT_DIR}/backend/tests/test_home_safety_remark_alarms_v1_20260529.py",
     "/app/tests/test_home_safety_remark_alarms_v1_20260529.py",
     "backend"),
    # ── 现有测试（加了 remark）──
    ("backend/tests/test_home_safety_v1.py",
     f"{PROJECT_DIR}/backend/tests/test_home_safety_v1.py",
     "/app/tests/test_home_safety_v1.py",
     "backend"),
    ("backend/tests/test_home_safety_v2.py",
     f"{PROJECT_DIR}/backend/tests/test_home_safety_v2.py",
     "/app/tests/test_home_safety_v2.py",
     "backend"),
    ("backend/tests/test_home_safety_v2_revision.py",
     f"{PROJECT_DIR}/backend/tests/test_home_safety_v2_revision.py",
     "/app/tests/test_home_safety_v2_revision.py",
     "backend"),
    ("backend/tests/test_home_safety_gwid_ephone_v1.py",
     f"{PROJECT_DIR}/backend/tests/test_home_safety_gwid_ephone_v1.py",
     "/app/tests/test_home_safety_gwid_ephone_v1.py",
     "backend"),
    ("backend/tests/test_home_safety_callback_datatype_v1.py",
     f"{PROJECT_DIR}/backend/tests/test_home_safety_callback_datatype_v1.py",
     "/app/tests/test_home_safety_callback_datatype_v1.py",
     "backend"),
    ("backend/tests/test_home_safety_member_v21.py",
     f"{PROJECT_DIR}/backend/tests/test_home_safety_member_v21.py",
     "/app/tests/test_home_safety_member_v21.py",
     "backend"),
    # ── h5-web ──
    ("h5-web/src/components/family/FamilyMemberTabs.tsx",
     f"{PROJECT_DIR}/h5-web/src/components/family/FamilyMemberTabs.tsx", None, None),
    ("h5-web/src/app/home-safety/components/AlarmList.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/home-safety/components/AlarmList.tsx", None, None),
    ("h5-web/src/app/home-safety/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/home-safety/page.tsx", None, None),
    # ── admin-web ──
    ("admin-web/src/app/(admin)/home-safety/page.tsx",
     f"{PROJECT_DIR}/admin-web/src/app/(admin)/home-safety/page.tsx", None, None),
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
    print(f"  upload {local} -> {remote}")
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


PYTEST_RC = 0


def main():
    global PYTEST_RC
    print(f"[deploy] connecting to {USER}@{HOST} ...")
    cli = ssh_connect()
    sftp = cli.open_sftp()
    try:
        # 1) 上传源码
        for local, remote_host, _docker_path, _kw in LOCAL_FILES:
            local_abs = os.path.abspath(local)
            if not os.path.exists(local_abs):
                raise FileNotFoundError(local_abs)
            upload_file(sftp, local_abs, remote_host)

        # 2) backend docker cp + restart
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
        for i in range(40):
            rc, out, _ = run(
                cli,
                f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost/autodev/{DEPLOY_ID}/api/health",
                check=False, quiet=True
            )
            if "200" in out:
                print(f"[deploy] backend ready after {i+1}s")
                break
            time.sleep(2)
        else:
            print("[deploy] backend health 超时，继续后续步骤")

        # 3) 跑 pytest（新 + 老回归）
        print("\n[deploy] === pytest home_safety remark + alarms (NEW) ===")
        rc, out, err = run(
            cli,
            f"docker exec {be_name} python -m pytest "
            "tests/test_home_safety_remark_alarms_v1_20260529.py "
            "-v --tb=short",
            sudo=True, check=False, timeout=600
        )
        if rc != 0:
            print("[deploy] !! NEW pytest 失败")
            PYTEST_RC = rc

        print("\n[deploy] === pytest home_safety 全套回归 ===")
        rc2, out2, _ = run(
            cli,
            f"docker exec {be_name} python -m pytest "
            "tests/test_home_safety_v1.py "
            "tests/test_home_safety_v2.py "
            "tests/test_home_safety_v2_revision.py "
            "tests/test_home_safety_gwid_ephone_v1.py "
            "tests/test_home_safety_callback_datatype_v1.py "
            "tests/test_home_safety_member_v21.py "
            "-v --tb=short",
            sudo=True, check=False, timeout=900
        )
        if rc2 != 0:
            print("[deploy] !! 回归 pytest 失败")
            PYTEST_RC = rc2 if PYTEST_RC == 0 else PYTEST_RC

        # 4) h5-web rebuild
        print("\n[deploy] === rebuild h5-web ===")
        run(cli, f"cd {PROJECT_DIR} && docker compose build h5-web && docker compose up -d h5-web",
            sudo=True, timeout=900)

        # 5) admin-web rebuild
        print("\n[deploy] === rebuild admin-web ===")
        run(cli, f"cd {PROJECT_DIR} && docker compose build admin-web && docker compose up -d admin-web",
            sudo=True, timeout=900)

        # 6) 重新 docker cp backend（防止 compose 重启后 backend 容器被替换）
        be_name2 = find_container(cli, "backend")
        if be_name2:
            print(f"[deploy] re-cp backend after compose: {be_name2}")
            for _local, remote_host, docker_path, kw in LOCAL_FILES:
                if kw == "backend" and docker_path:
                    run(cli, f"docker cp {remote_host} {be_name2}:{docker_path}", sudo=True, check=False)
            run(cli, f"docker restart {be_name2}", sudo=True, check=False)
            time.sleep(5)

        # 7) smoke 测试
        print("\n[deploy] === smoke ===")
        base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
        for path in [
            "/api/health",
            "/home-safety/",
            "/admin/home-safety/",
            "/api/home_safety/members",  # 401（鉴权）
            "/api/family/members",  # 401（鉴权）
        ]:
            rc, out, _ = run(
                cli,
                f"curl -sk -o /dev/null -w '%{{http_code}}' {base}{path}",
                check=False, quiet=True
            )
            print(f"  GET {path} -> {out.strip()}")

    finally:
        try:
            sftp.close()
        except Exception:
            pass
        cli.close()
        print("[deploy] done.")


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
