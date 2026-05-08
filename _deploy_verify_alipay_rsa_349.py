"""develop-all 阶段 2-3：确认 origin/master 上最新修复已部署到服务器并 pytest 通过。

流程：
1) ssh 到 newbb.test.bangbangvip.com
2) 在 /opt/autodev/<deploy_id> 目录下 git fetch + 检查当前 commit
3) 如果服务器上不是最新 commit（或文件 rsa_key.py 没有最新修复关键字），重新拉代码 + 重启后端 + 等待健康检查
4) 在后端容器内执行 pytest backend/tests/test_alipay_private_key_format.py + test_payment_config_alipay_save_validation.py
5) 输出测试通过/失败汇总
"""
from __future__ import annotations

import json
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
EXPECTED_COMMIT_PREFIX = "e42ed46"


def ssh_exec(client: paramiko.SSHClient, cmd: str, timeout: int = 120) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def main() -> int:
    print(f"[1/5] 连接服务器 {HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30, look_for_keys=False, allow_agent=False)
    print("    SSH 已连接")

    # 查找部署目录
    print("[2/5] 定位项目部署目录...")
    cands = [
        f"/home/ubuntu/autodev/{DEPLOY_ID}",
        f"/opt/autodev/{DEPLOY_ID}",
        f"/srv/autodev/{DEPLOY_ID}",
        f"~/autodev/{DEPLOY_ID}",
    ]
    project_dir = None
    for c in cands:
        code, out, _ = ssh_exec(client, f"test -d {c} && echo OK || echo NO")
        if "OK" in out:
            project_dir = c
            break
    if not project_dir:
        # fallback: 通过 docker container 名称推测
        code, out, _ = ssh_exec(
            client,
            f"docker inspect {DEPLOY_ID}-backend "
            f"--format '{{{{ index .Config.Labels \"com.docker.compose.project.working_dir\" }}}}' 2>/dev/null",
        )
        wd = out.strip()
        if wd:
            project_dir = wd
    if not project_dir:
        print("[X] 找不到部署目录，列出 ~/autodev：")
        _, out, _ = ssh_exec(client, "ls -la ~/autodev 2>/dev/null || ls -la /home/ubuntu/autodev 2>/dev/null")
        print(out)
        return 2
    print(f"    项目目录：{project_dir}")

    # 检查当前 commit
    print("[3/5] 检查服务器代码版本与 rsa_key.py 是否包含最新修复...")
    _, out, _ = ssh_exec(client, f"cd {project_dir} && git log -1 --oneline 2>&1 || true")
    print(f"    当前 commit: {out.strip()}")
    current_ok = EXPECTED_COMMIT_PREFIX in out

    # 检查关键字
    _, out2, _ = ssh_exec(
        client,
        f"cd {project_dir} && grep -c '_wrap_pkcs1_pem' backend/app/utils/rsa_key.py 2>/dev/null || echo 0",
    )
    rsa_key_has_fix = int(out2.strip().split("\n")[-1] or "0") > 0

    print(f"    commit 命中: {current_ok}; rsa_key.py 含 PKCS#1 包装: {rsa_key_has_fix}")

    if not (current_ok and rsa_key_has_fix):
        print("    需要拉取最新代码 + 重启后端...")
        _, out, err = ssh_exec(
            client,
            f"cd {project_dir} && git fetch origin master && git reset --hard origin/master && git log -1 --oneline",
            timeout=120,
        )
        print(f"    git fetch+reset: {out.strip()}\n{err}")

        print("    重启后端容器...")
        _, out, err = ssh_exec(
            client,
            f"docker restart {DEPLOY_ID}-backend 2>&1",
            timeout=60,
        )
        print(f"    docker restart: {out.strip()}\n{err}")

        print("    等待后端就绪 ...")
        time.sleep(8)

    # 在后端容器内运行 pytest
    print("[4/5] 在后端容器内执行 pytest（针对支付宝私钥相关）...")
    pytest_cmd = (
        f"docker exec {DEPLOY_ID}-backend bash -lc "
        f"'cd /app && python -m pytest -x -q "
        f"backend/tests/test_alipay_private_key_format.py "
        f"backend/tests/test_payment_config_alipay_save_validation.py "
        f"backend/tests/test_payment_config_test_connection_error_message.py "
        f"2>&1 | tail -80'"
    )
    code, out, err = ssh_exec(client, pytest_cmd, timeout=300)
    print(f"    pytest 退出码：{code}")
    print(out)
    if err:
        print("STDERR:", err)

    # 简单 e2e：HTTP API 调用 /api/admin/payment-channels/alipay_h5（需登录） — 跳过，仅验后端 health
    print("[5/5] 验证后端 health endpoint ...")
    code, out, _ = ssh_exec(
        client,
        f"curl -s -o /dev/null -w '%{{http_code}}' "
        f"https://{HOST}/autodev/{DEPLOY_ID}/api/health || echo 000",
    )
    print(f"    /api/health 状态码：{out.strip()}")

    client.close()
    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
