"""[PRD-FAMILY-MEMBER-STATE-MACHINE-V1 2026-05-29] 部署脚本

1. SSH 上传 backend/app/api/family_member_v2.py + main.py + tests + h5-web 新页面
2. 后端：docker cp + restart
3. h5-web：rebuild + up -d
4. 容器内 pytest 跑新测试
5. HTTPS smoke：/api/health, /api/family/member/quota（无 token），/health-profile/archive-list/
"""
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

REMOTE_PROJECT = f"/home/ubuntu/{DEPLOY_ID}"
REMOTE_STATIC = f"/home/ubuntu/{DEPLOY_ID}_static"


def ssh_connect():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASS, timeout=30)
    return cli


def run(cli, cmd, timeout=300, allow_fail=False):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    print(f"exit={code}")
    if code != 0 and not allow_fail:
        raise RuntimeError(f"command failed: {cmd}")
    return out + err, code


def upload(sftp, local, remote):
    print(f"upload {local} -> {remote}")
    sftp.put(local, remote)


def main():
    print(f"=== 部署 {DEPLOY_ID} ===")
    cli = ssh_connect()
    try:
        sftp = cli.open_sftp()
        # 1) 确认远程项目目录
        out, _ = run(cli, f"ls -la {REMOTE_PROJECT}")

        # 2) 上传后端文件
        try:
            sftp.stat(f"{REMOTE_PROJECT}/backend/app/api/family_member_v2.py")
        except Exception:
            pass
        upload(sftp, "backend/app/api/family_member_v2.py", f"{REMOTE_PROJECT}/backend/app/api/family_member_v2.py")
        upload(sftp, "backend/app/main.py", f"{REMOTE_PROJECT}/backend/app/main.py")
        upload(sftp, "backend/tests/test_family_member_state_machine_v1_20260529.py",
               f"{REMOTE_PROJECT}/backend/tests/test_family_member_state_machine_v1_20260529.py")

        # 3) 上传 h5-web 文件
        run(cli, f"mkdir -p {REMOTE_PROJECT}/h5-web/src/app/health-profile/archive-list")
        upload(sftp, "h5-web/src/app/health-profile/archive-list/page.tsx",
               f"{REMOTE_PROJECT}/h5-web/src/app/health-profile/archive-list/page.tsx")

        # 4) docker cp 后端文件到容器
        container = f"{DEPLOY_ID}-backend"
        run(cli, f"docker cp {REMOTE_PROJECT}/backend/app/api/family_member_v2.py {container}:/app/app/api/family_member_v2.py")
        run(cli, f"docker cp {REMOTE_PROJECT}/backend/app/main.py {container}:/app/app/main.py")
        run(cli, f"docker cp {REMOTE_PROJECT}/backend/tests/test_family_member_state_machine_v1_20260529.py {container}:/app/tests/test_family_member_state_machine_v1_20260529.py", allow_fail=True)
        # 重启后端
        run(cli, f"docker restart {container}", timeout=60)
        # 等待
        time.sleep(8)

        # 5) 跑测试
        out, code = run(
            cli,
            f"docker exec {container} sh -c 'cd /app && python -m pytest tests/test_family_member_state_machine_v1_20260529.py -v --tb=short 2>&1 | tail -100'",
            timeout=300, allow_fail=True,
        )
        if "passed" not in out and "failed" not in out:
            print("⚠ 测试结果异常")
        else:
            print("✓ 测试完成")

        # 6) 重建 h5-web
        print("\n=== 重建 h5-web ===")
        run(cli, f"cd {REMOTE_PROJECT} && docker compose build h5-web 2>&1 | tail -20",
            timeout=600, allow_fail=True)
        run(cli, f"cd {REMOTE_PROJECT} && docker compose up -d h5-web 2>&1 | tail -10", allow_fail=True)
        time.sleep(10)

        # 7) HTTPS smoke
        print("\n=== smoke ===")
        run(cli, f"curl -sk -o /dev/null -w '%{{http_code}}\\n' {BASE_URL}/api/health")
        run(cli, f"curl -sk -o /dev/null -w '%{{http_code}}\\n' {BASE_URL}/api/family/member/quota")
        run(cli, f"curl -sk -o /dev/null -w '%{{http_code}}\\n' {BASE_URL}/health-profile/archive-list/")
        run(cli, f"curl -sk -o /dev/null -w '%{{http_code}}\\n' {BASE_URL}/health-profile/")

        print("\n=== 部署完成 ===")
    finally:
        cli.close()


if __name__ == "__main__":
    main()
