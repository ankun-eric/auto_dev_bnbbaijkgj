"""[PRD-HEALTH-ARCHIVE-OPTIM-V1 2026-05-18] 部署：SFTP 上传 + docker compose 重建。"""
from __future__ import annotations
import os, paramiko, posixpath

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"

FILES = [
    # backend
    "backend/app/api/health_archive_optim_v1.py",
    "backend/app/api/medication_plans_v1.py",
    "backend/app/main.py",
    "backend/app/models/models.py",
    "backend/app/services/prd_health_archive_optim_v1_migration.py",
    "backend/app/services/schema_sync.py",
    "backend/tests/test_health_archive_optim_v1_20260518.py",
    # h5-web
    "h5-web/src/app/health-profile/page.tsx",
    "h5-web/src/components/health-profile-v5/CareReminderBlock.tsx",
    "h5-web/src/app/family-guardian-list/page.tsx",
    "h5-web/src/app/family-guardian-list/[targetId]/page.tsx",
]


def run(c, cmd, t=900, ignore=False):
    print(f"\n$ {cmd[:220]}")
    _, so, se = c.exec_command(cmd, timeout=t + 60, get_pty=False)
    so.channel.settimeout(t + 60); se.channel.settimeout(t + 60)
    out = so.read().decode("utf-8", errors="replace")
    err = se.read().decode("utf-8", errors="replace")
    rc = so.channel.recv_exit_status()
    if out.strip(): print(out[-3500:])
    if err.strip(): print("STDERR:", err[-1500:])
    if rc != 0 and not ignore:
        raise RuntimeError(f"cmd failed (rc={rc})")
    return rc, out, err


def ensure_dir(sftp, c, remote_path):
    parts = remote_path.strip("/").split("/")
    cur = ""
    for p in parts:
        cur = cur + "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            run(c, f"mkdir -p '{cur}'", t=30)


def main():
    base = os.path.abspath(os.path.dirname(__file__) + "/..")
    print(f"Local base: {base}")
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, PORT, USER, PWD, timeout=30, allow_agent=False, look_for_keys=False)
    try:
        sftp = cli.open_sftp()
        for rel in FILES:
            local = os.path.join(base, rel.replace("/", os.sep))
            if not os.path.exists(local):
                print(f"  [SKIP] {local}")
                continue
            remote = posixpath.join(PROJ_DIR, rel)
            ensure_dir(sftp, cli, posixpath.dirname(remote))
            sftp.put(local, remote)
            print(f"  uploaded -> {remote}")
        sftp.close()

        # 重建 backend + h5-web
        run(cli, f"cd {PROJ_DIR} && docker compose build backend h5-web 2>&1 | tail -100", t=1800)
        run(cli, f"cd {PROJ_DIR} && docker compose up -d backend h5-web", t=300)
        run(cli, f"sleep 30 && docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {DEPLOY_ID}")
        run(cli, f"docker logs --tail 80 {DEPLOY_ID}-backend 2>&1 | tail -80", ignore=True)
    finally:
        cli.close()


if __name__ == "__main__":
    main()
