"""[BUGFIX-GUARDIAN-LIST-CONSISTENCY-V2 2026-05-29] 守护人体系 v1.3.2 补丁部署脚本

涉及文件：
- backend/app/api/guardian_system_v13.py    → docker cp + restart（_calc_used_quota 新公式）
- backend/tests/test_guardian_bugfix_v2_20260529.py → docker cp（测试）
- h5-web/src/utils/nicknameValidator.ts     → rebuild h5-web（新增）
- h5-web/src/app/family-invite/page.tsx     → rebuild h5-web（G1）
- h5-web/src/app/health-profile/i-guard/page.tsx → rebuild h5-web（D7 纯特殊字符校验）
- h5-web/src/components/health-profile-v5/NewFamilyMemberModal.tsx → rebuild h5-web（D5）
- h5-web/src/components/ai-chat/ConsultTargetPicker.tsx → rebuild h5-web（G3）

策略：
1) backend 走 docker cp 热更 + docker restart
2) h5-web 走 docker compose build + up -d
3) 部署后跑 pytest 做 v2 用例回归
"""
from __future__ import annotations
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

LOCAL_FILES = [
    ("backend/app/api/guardian_system_v13.py",
     f"{PROJECT_DIR}/backend/app/api/guardian_system_v13.py",
     "/app/app/api/guardian_system_v13.py",
     "backend"),
    ("backend/tests/test_guardian_bugfix_v2_20260529.py",
     f"{PROJECT_DIR}/backend/tests/test_guardian_bugfix_v2_20260529.py",
     "/app/tests/test_guardian_bugfix_v2_20260529.py",
     "backend"),
    # H5 - 走 rebuild，仅同步源码到主机
    ("h5-web/src/utils/nicknameValidator.ts",
     f"{PROJECT_DIR}/h5-web/src/utils/nicknameValidator.ts",
     None, None),
    ("h5-web/src/app/family-invite/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/family-invite/page.tsx",
     None, None),
    ("h5-web/src/app/health-profile/i-guard/page.tsx",
     f"{PROJECT_DIR}/h5-web/src/app/health-profile/i-guard/page.tsx",
     None, None),
    ("h5-web/src/components/health-profile-v5/NewFamilyMemberModal.tsx",
     f"{PROJECT_DIR}/h5-web/src/components/health-profile-v5/NewFamilyMemberModal.tsx",
     None, None),
    ("h5-web/src/components/ai-chat/ConsultTargetPicker.tsx",
     f"{PROJECT_DIR}/h5-web/src/components/ai-chat/ConsultTargetPicker.tsx",
     None, None),
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


def run(cli, cmd, *, timeout=180, sudo=False, check=True, quiet=False):
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


def main():
    print(f"=== Connecting to {USER}@{HOST}:{PORT} ===")
    cli = ssh_connect()

    print("\n=== 1. Upload source files to host ===")
    sftp = cli.open_sftp()
    for local, host_dst, _, _ in LOCAL_FILES:
        host_dir = host_dst.rsplit("/", 1)[0]
        run(cli, f"mkdir -p {host_dir}", check=False, quiet=True)
        print(f"  upload {local} -> {host_dst}")
        sftp.put(local, host_dst)
    sftp.close()

    print("\n=== 2. Locate backend container ===")
    be = find_container(cli, "backend") or f"{DEPLOY_ID}-backend"
    print(f"[+] backend = {be}")

    print("\n=== 3. docker cp backend source files ===")
    for local, host_dst, container_dst, container in LOCAL_FILES:
        if not container_dst or container != "backend":
            continue
        print(f"  cp {host_dst} -> {be}:{container_dst}")
        run(cli, f"docker cp {host_dst} {be}:{container_dst}")

    print("\n=== 4. Restart backend ===")
    run(cli, f"docker restart {be}")
    for i in range(30):
        time.sleep(2)
        rc, out, _ = run(
            cli,
            f"docker exec {be} sh -c 'wget -qO- http://localhost:8000/api/health 2>&1 || echo NOTREADY'",
            check=False, quiet=True,
        )
        if "NOTREADY" not in out and out.strip():
            print(f"[+] backend ready: {out[:200]}")
            break
        print(f"[poll {i}] waiting backend ready ...")

    print("\n=== 5. Run pytest (guardian_bugfix_v1 + v2 一并回归) ===")
    rc, out, err = run(
        cli,
        f"docker exec {be} sh -c 'cd /app && python -m pytest "
        f"tests/test_guardian_bugfix_v1_20260529.py "
        f"tests/test_guardian_bugfix_v2_20260529.py "
        f"-v --tb=short 2>&1'",
        timeout=900, check=False,
    )
    print("\n=== pytest summary ===")
    lines = (out + err).splitlines()
    for l in lines[-200:]:
        print(l)
    pytest_rc = rc

    print("\n=== 6. Rebuild h5-web ===")
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -40",
        timeout=1200, check=False)
    run(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -10",
        timeout=180, check=False)

    print("\n=== 6.1 h5-web rebuild 会重启 backend, 再次 docker cp ===")
    time.sleep(3)
    for local, host_dst, container_dst, container in LOCAL_FILES:
        if not container_dst or container != "backend":
            continue
        run(cli, f"docker cp {host_dst} {be}:{container_dst}", check=False)
    run(cli, f"docker restart {be}", check=False)
    for i in range(20):
        time.sleep(2)
        rc, out, _ = run(
            cli,
            f"docker exec {be} sh -c 'wget -qO- http://localhost:8000/api/health 2>&1 || echo NOTREADY'",
            check=False, quiet=True,
        )
        if "NOTREADY" not in out and out.strip():
            print(f"[+] backend ready after rebuild: {out[:200]}")
            break

    print("\n=== 7. Smoke test ===")
    base = f"https://localhost/autodev/{DEPLOY_ID}"
    for path, label in [
        ("/api/health", "backend health"),
        ("/health-profile/i-guard/", "H5 我守护的人"),
        ("/family-invite/", "H5 邀请页"),
        ("/api/family/members", "API family members（期望 401）"),
        ("/api/guardian/v13/family/list", "API family list v13（期望 401）"),
    ]:
        run(cli, f"curl -sk -o /dev/null -w '{label} {path} -> %{{http_code}}\\n' --max-time 15 {base}{path}",
            check=False)

    cli.close()
    print("\n=== DEPLOY DONE ===")
    return pytest_rc


if __name__ == "__main__":
    try:
        rc = main()
        sys.exit(0 if rc == 0 else 2)
    except Exception as e:
        print(f"\n[FATAL] {e}", file=sys.stderr)
        sys.exit(1)
