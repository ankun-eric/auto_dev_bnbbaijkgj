"""[2026-05-03 PRD「我的订单与售后状态体系优化」] 部署 + 容器内 pytest + URL 自检。

- SSH 到 newbb.test.bangbangvip.com (ubuntu / Newbang888)
- 远程项目目录：/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ 或同名兜底目录
- git fetch origin master + reset --hard
- docker compose build backend admin-web h5-web
- docker compose up -d --force-recreate
- 容器内跑 pytest tests/test_orders_aftersales_v3.py（先安装 pytest 依赖）
- 关键 URL 自检
"""
from __future__ import annotations

import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

CANDIDATE_DIRS = [
    f"/home/ubuntu/{DEPLOY_ID}",
    "/home/ubuntu/auto_dev_bnbbaijkgj",
    "/home/ubuntu/projects/auto_dev_bnbbaijkgj",
    "/home/ubuntu/bnbbaijkgj",
]


def run(ssh, cmd, timeout=600):
    print(f"\n>>> {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip()[-6000:])
    if err.strip():
        print(f"[stderr]\n{err.rstrip()[-2000:]}")
    print(f"<<< exit={code}")
    return code, out, err


def find_project_dir(ssh):
    for d in CANDIDATE_DIRS:
        code, out, _ = run(ssh, f"test -d {d} && echo OK_HIT || echo NO_DIR")
        if "OK_HIT" in out:
            return d
    code, out, _ = run(ssh,
        f"docker inspect {DEPLOY_ID}-backend "
        f"--format '{{{{index .Config.Labels \"com.docker.compose.project.working_dir\"}}}}' 2>/dev/null || true")
    line = (out or "").strip().splitlines()[-1] if out and out.strip() else ""
    if line and line.startswith("/"):
        return line
    raise RuntimeError("无法定位远程项目目录")


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"连接 {USER}@{HOST} ...")
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        proj = find_project_dir(ssh)
        print(f"远程项目目录：{proj}")

        # 1) 同步代码
        run(ssh, f"cd {proj} && git fetch origin master 2>&1 | tail -10")
        run(ssh, f"cd {proj} && git reset --hard origin/master 2>&1 | tail -5")
        _, head_out, _ = run(ssh, f"cd {proj} && git log -1 --format='%H %s'")
        print(f"远程 HEAD: {head_out.strip()}")

        # 2) 构建（仅本次改动的三个服务）
        for svc in ("backend", "admin-web", "h5-web"):
            run(ssh,
                f"cd {proj} && docker compose build {svc} 2>&1 | tail -50",
                timeout=1500)

        # 3) 启动
        run(ssh,
            f"cd {proj} && docker compose up -d --force-recreate backend admin-web h5-web 2>&1 | tail -20",
            timeout=300)

        # 4) 等待健康
        time.sleep(20)
        run(ssh, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

        # 5) 容器内跑新的 V3 pytest（含 V2 回归）
        time.sleep(10)
        # 容器内安装 pytest 依赖（生产 Dockerfile 通常不带 pytest）
        run(ssh,
            f"docker exec {DEPLOY_ID}-backend pip install -q pytest pytest-asyncio aiosqlite httpx 2>&1 | tail -10",
            timeout=300)
        code, pytest_out, _ = run(ssh,
            f"docker exec {DEPLOY_ID}-backend python -m pytest "
            f"tests/test_orders_status_v2.py tests/test_orders_aftersales_v3.py -q 2>&1 | tail -40",
            timeout=900)
        pytest_ok = (code == 0)

        # 6) URL 自检
        url_results = {}
        for path in [
            "/api/health",
            "/api/orders/unified",                       # 期望 401（未带 token）
            "/api/orders/unified/counts",                # 期望 401
            "/api/admin/orders/v2/enums",                # 期望 401（含 aftersales_logical_status 4 值）
            "/admin/",
            "/admin/product-system/orders",              # 后台订单页（含新文案）
            "/profile",                                  # H5 我的页面（含新已完成入口）
            "/unified-orders",                           # H5 订单列表（4 个二级 Tab 新文案）
            "/refund-list",                              # H5 退款独立列表（4 个新筛选）
        ]:
            _, out, _ = run(ssh,
                f"curl -ksL -o /dev/null -w '%{{http_code}}' {BASE_URL}{path}")
            code_val = (out or "").strip().splitlines()[-1] if out.strip() else "?"
            url_results[path] = code_val
        print("\n=== URL 自检结果 ===")
        for p, c in url_results.items():
            print(f"  {p:45s} -> {c}")

        url_ok = all(c in ("200", "302", "303", "307", "308", "401", "403") for c in url_results.values())

        print(f"\n=== 最终结果: pytest={'OK' if pytest_ok else 'FAIL'}  url={'OK' if url_ok else 'FAIL'} ===")
        return 0 if (pytest_ok and url_ok) else 1
    finally:
        ssh.close()


if __name__ == "__main__":
    sys.exit(main())
