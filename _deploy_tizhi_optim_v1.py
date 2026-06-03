"""[PRD-TIZHI-OPTIM-V1 2026-06-01] 体质测评优化 部署脚本.

通过 paramiko SFTP 直传改动文件到服务器项目目录，再 docker compose 重建受影响服务。
GitHub 在服务器侧 fetch 超时（沿用历史降级方案），故走 SFTP 直传。
"""
import os
import sys
import stat
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL = os.path.dirname(os.path.abspath(__file__))

# 改动 / 新增文件（相对路径，正斜杠）
FILES = [
    # backend
    "backend/app/api/constitution.py",
    "backend/app/main.py",
    "backend/app/models/models.py",
    "backend/app/services/constitution_content_seed.py",
    "backend/tests/test_tizhi_optim_v1_20260601.py",
    # h5
    "h5-web/src/app/tcm/page.tsx",
    "h5-web/src/app/tcm/result/[id]/page.tsx",
    "h5-web/src/components/ai-chat/UniversalQuestionnaireResultCard.tsx",
    # admin
    "admin-web/src/app/(admin)/layout.tsx",
    "admin-web/src/app/(admin)/constitution-content/page.tsx",
]


def get_client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30,
              look_for_keys=False, allow_agent=False)
    return c


def run(c, cmd, timeout=900):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def sftp_mkdirs(sftp, remote_dir):
    parts = remote_dir.split("/")
    cur = ""
    for p in parts:
        if not p:
            cur += "/"
            continue
        cur = cur.rstrip("/") + "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)


def upload(c):
    sftp = c.open_sftp()
    for rel in FILES:
        local_path = os.path.join(LOCAL, rel.replace("/", os.sep))
        remote_path = f"{REMOTE}/{rel}"
        if not os.path.exists(local_path):
            print(f"!! MISSING LOCAL: {local_path}")
            continue
        sftp_mkdirs(sftp, os.path.dirname(remote_path))
        sftp.put(local_path, remote_path)
        print(f"  uploaded {rel}")
    sftp.close()


def main():
    c = get_client()
    try:
        print("=== 1. 上传改动文件 ===")
        upload(c)

        print("=== 2. 生成 BUILD_COMMIT ===")
        rc, out, err = run(c, f"cd {REMOTE} && git rev-parse HEAD 2>/dev/null || echo sftp-tizhi-optim-v1")
        commit = (out.strip().splitlines() or ["sftp-tizhi-optim-v1"])[-1]
        run(c, f"cd {REMOTE} && echo 'BUILD_COMMIT={commit}' >> .env")
        print(f"  BUILD_COMMIT={commit}")

        print("=== 3. 重建 backend / admin / h5 ===")
        rc, out, err = run(
            c,
            f"cd {REMOTE} && docker compose -f docker-compose.prod.yml build --no-cache backend admin-web h5-web 2>&1 | tail -40",
            timeout=1800,
        )
        print(out)
        if err.strip():
            print("STDERR:", err[-2000:])
        print(f"  build rc={rc}")
        if rc != 0:
            print("!! BUILD FAILED")
            return 1

        print("=== 4. 启动容器 ===")
        rc, out, err = run(
            c,
            f"cd {REMOTE} && docker compose -f docker-compose.prod.yml up -d backend admin-web h5-web 2>&1 | tail -20",
            timeout=600,
        )
        print(out, err[-1000:] if err else "")

        print("=== 5. 等待健康 + gateway 重连网络 ===")
        run(c, "sleep 20")
        # gateway 容器名探测
        rc, out, err = run(c, "docker ps --format '{{.Names}}' | grep -i gateway")
        gw = (out.strip().splitlines() or [""])[0].strip()
        print(f"  gateway={gw}")
        if gw:
            run(c, f"docker network connect {DEPLOY_ID}-network {gw} 2>/dev/null || true")
            run(c, f"docker exec {gw} nginx -s reload 2>/dev/null || true")
        rc, out, err = run(c, f"cd {REMOTE} && docker compose -f docker-compose.prod.yml ps 2>&1 | tail -10")
        print(out)
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
