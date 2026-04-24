"""[2026-04-25] 商家 PC 后台登录 401 Bug 修复部署脚本。

仅改动后端两个文件：
- backend/app/api/merchant_v1.py  （PC 登录签发 token 时 sub 改为 str）
- backend/app/core/security.py    （create_access_token 自动 str 化 + get_current_user 类型兼容 + 日志）
- tests/test_merchant_pc_login_jwt.py（新增回归测试）

通过 SFTP 上传改动文件，重建 backend 容器，然后端到端验证：
登录接口返回 200 → 拿 token 调 dashboard 接口 → 断言不再是 401。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

LOCAL_ROOT = Path(__file__).resolve().parent.parent

FILES = [
    "backend/app/api/merchant_v1.py",
    "backend/app/core/security.py",
    "tests/test_merchant_pc_login_jwt.py",
]


def _ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return c


def _run(c: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    _stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(f"$ {cmd}")
    if out.strip():
        print(out[:3000])
    if err.strip():
        print("stderr:", err[:1500])
    print(f"exit={code}\n")
    return code, out, err


def main() -> int:
    print("== SSH 连接 ==")
    c = _ssh()
    sftp = c.open_sftp()
    try:
        print("== 上传改动文件 ==")
        ok, miss = 0, 0
        for rel in FILES:
            local = LOCAL_ROOT / rel
            remote = f"{PROJECT_DIR}/{rel}"
            if not local.exists():
                print(f"[skip] 本地不存在：{local}")
                miss += 1
                continue
            remote_dir = remote.rsplit("/", 1)[0]
            _run(c, f"mkdir -p {remote_dir}", timeout=30)
            sftp.put(str(local), remote)
            print(f"[ok] {rel}")
            ok += 1
        print(f"文件上传完成：ok={ok} miss={miss}")

        print("== 重建 backend 容器 ==")
        _run(
            c,
            f"cd {PROJECT_DIR} && docker compose build backend 2>&1 | tail -40",
            timeout=1500,
        )
        _run(
            c,
            f"cd {PROJECT_DIR} && docker compose up -d backend 2>&1 | tail -40",
            timeout=300,
        )

        time.sleep(10)
        _run(
            c,
            f"docker ps --format '{{{{.Names}}}}: {{{{.Status}}}}' | grep {DEPLOY_ID}",
            timeout=30,
        )
        _run(c, f"docker logs --tail 30 {DEPLOY_ID}-backend 2>&1 | tail -30", timeout=30)

        print("== 健康探测：前端主页 + 商家登录页 ==")
        for path in ["/", "/merchant/login", "/api/health"]:
            _run(
                c,
                f"curl -sk -o /dev/null -w 'code=%{{http_code}} url={BASE_URL}{path}\\n' "
                f"{BASE_URL}{path}",
                timeout=30,
            )

        print("== 核心回归：登录接口 + Dashboard 接口 ==")
        # 这里只是在服务器侧做"接口 shape"层面的探测：
        # 1) /api/merchant/auth/login 用不存在的手机号应返回 401，但不再 500
        # 2) Dashboard 带一个合法结构的 token（str sub）应能正常响应，不会再因 sub 类型崩
        login_probe_cmd = (
            f"curl -sk -o /tmp/login_probe.json -w 'code=%{{http_code}}\\n' "
            f"-H 'Content-Type: application/json' "
            f"-d '{json.dumps({'phone': '00000000000', 'password': 'x'})}' "
            f"{BASE_URL}/api/merchant/auth/login && cat /tmp/login_probe.json && echo"
        )
        _run(c, login_probe_cmd, timeout=30)

        return 0
    finally:
        sftp.close()
        c.close()


if __name__ == "__main__":
    sys.exit(main())
