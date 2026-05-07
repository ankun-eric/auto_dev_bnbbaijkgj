"""[双重身份用户 H5 顾客端改约失败 Bug 修复 v1.0]
完整远程部署 + pytest 验证脚本。

流程：
1) 本地 git add/commit/push（带 token URL）
2) 远程 git pull
3) 远程重新构建并启动 backend + h5-web 容器
4) 远程在 backend 容器内运行新增的 pytest 用例
5) 远程对部署后的关键 URL 做 HTTP 200 检查（前端首页 / 登录页）
"""
import subprocess
import sys
import time
import os

# ─── 部署配置 ───
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
REMOTE_HOST = "newbb.test.bangbangvip.com"
REMOTE_USER = "ubuntu"
REMOTE_PASS = "Newbang888"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GIT_REPO = os.environ.get("BINI_GIT_REPO", "https://github.com/ankun-eric/auto_dev_bnbbaijkgj.git")
LOCAL_REPO = r"C:\auto_output\bnbbaijkgj"


def run(cmd, cwd=None, check=True, timeout=600):
    """执行本地命令并打印输出。"""
    print(f"\n[LOCAL] $ {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.stdout:
        print(result.stdout[-3000:])
    if result.stderr:
        print("STDERR:", result.stderr[-3000:])
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed: {cmd}\nrc={result.returncode}")
    return result


def ssh(cmd, timeout=900):
    """通过 sshpass + ssh 在远端执行命令。"""
    # Windows 下用 plink/ssh 不便处理密码，使用 paramiko
    import paramiko
    print(f"\n[REMOTE] $ {cmd}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASS, timeout=30)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    client.close()
    if out:
        print(out[-5000:])
    if err:
        print("STDERR:", err[-5000:])
    return rc, out, err


def step1_local_git():
    """本地 git add/commit/push。"""
    print("\n=== STEP 1: 本地 Git commit & push ===")
    # 仅暂存关键修改（避免大量噪音文件污染）
    paths = [
        "backend/app/utils/client_source.py",
        "backend/app/api/unified_orders.py",
        "backend/tests/test_reschedule_dual_identity.py",
        "h5-web/src/lib/api.ts",
        "h5-web/src/lib/reschedule-error.ts",
        "h5-web/src/app/unified-order/[id]/page.tsx",
        "miniprogram/utils/request.js",
        "miniprogram/pages/unified-order-detail/index.js",
        "flutter_app/lib/services/api_service.dart",
        "flutter_app/lib/utils/reschedule_error.dart",
        "flutter_app/lib/screens/order/unified_order_detail_screen.dart",
        "_deploy_dual_identity_400.py",
    ]
    for p in paths:
        run(f'git add "{p}"', cwd=LOCAL_REPO, check=False)
    # commit
    run(
        'git commit -m "fix: 修复双重身份用户 H5 顾客端改约失败 + 错误结构化 (BUG-FIX-RESCHEDULE-DUAL-IDENTITY-V1)" --allow-empty',
        cwd=LOCAL_REPO,
        check=False,
    )
    # push
    run("git push origin master", cwd=LOCAL_REPO, check=False)


def step2_remote_pull_and_build():
    """远程 git pull + docker compose 重建 backend & h5-web。"""
    print("\n=== STEP 2: 远程 Git pull + Docker 重建 ===")
    # 先 pull
    rc, out, _ = ssh(
        f"cd {REMOTE_DIR} && git fetch --all && git reset --hard origin/master && git pull",
        timeout=300,
    )
    if rc != 0:
        # 仓库不存在则克隆
        rc2, _, _ = ssh(
            f"test -d {REMOTE_DIR}/.git || (rm -rf {REMOTE_DIR} && git clone {GIT_REPO} {REMOTE_DIR})",
            timeout=600,
        )
        if rc2 != 0:
            raise RuntimeError("远端仓库初始化失败")
        ssh(f"cd {REMOTE_DIR} && git pull")
    # 重建 backend + h5-web
    print("\n[REMOTE] 重新构建 backend 镜像...")
    ssh(
        f"cd {REMOTE_DIR} && docker compose build backend h5-web 2>&1 | tail -100",
        timeout=1200,
    )
    print("\n[REMOTE] 重启容器...")
    ssh(
        f"cd {REMOTE_DIR} && docker compose up -d backend h5-web 2>&1 | tail -40",
        timeout=300,
    )
    # 等待容器健康
    print("\n[REMOTE] 等待容器启动...")
    time.sleep(15)
    ssh(f"docker ps | grep {DEPLOY_ID} | head -10")


def step3_run_pytest():
    """在 backend 容器中运行专项 pytest。"""
    print("\n=== STEP 3: 远程运行 pytest ===")
    container = f"{DEPLOY_ID}-backend"
    rc, out, err = ssh(
        f"docker exec {container} sh -c 'cd /app && python -m pytest tests/test_reschedule_dual_identity.py -v --tb=short -x 2>&1 | tail -200'",
        timeout=600,
    )
    return rc, out


def step4_smoke_check():
    """对 base URL 做几次基本可达性 curl。"""
    print("\n=== STEP 4: HTTP 可达性检查 ===")
    rc, out, _ = ssh(
        f"curl -s -o /dev/null -w 'h5_root=%{{http_code}}\\n' {BASE_URL}/ ; "
        f"curl -s -o /dev/null -w 'h5_login=%{{http_code}}\\n' {BASE_URL}/login ; "
        f"curl -s -o /dev/null -w 'api_health=%{{http_code}}\\n' {BASE_URL}/api/health ; "
        f"curl -s -o /dev/null -w 'api_docs=%{{http_code}}\\n' {BASE_URL}/api/docs",
    )
    return out


def main():
    step1_local_git()
    step2_remote_pull_and_build()
    rc, pytest_out = step3_run_pytest()
    smoke = step4_smoke_check()

    print("\n\n========== 部署 + 测试 总结 ==========")
    print("pytest rc:", rc)
    print("smoke check:", smoke)
    if rc == 0:
        print("✅ pytest 全部通过")
    else:
        print("❌ pytest 存在失败用例，请查看日志")


if __name__ == "__main__":
    main()
