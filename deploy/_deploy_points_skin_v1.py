# -*- coding: utf-8 -*-
"""
PRD-POINTS-SKIN-V1 — 积分模块视觉换肤 部署 + 服务器自动化测试脚本

执行内容：
1. SSH 到服务器，git pull origin master 拉取最新代码
2. docker compose build --no-cache h5-web，重建 h5-web 镜像
3. docker compose up -d 启动新容器
4. 等待 30 秒待容器就绪
5. 通过 HTTP 自动化验证 6 个积分页面可达 + 关键换肤标记出现在容器构建产物中
"""
import io
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL_PATH = f"/autodev/{DEPLOY_ID}"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def run(ssh, cmd, timeout=900):
    """Run a shell command remotely and stream output."""
    print(f"\n$ {cmd}")
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    out_buf = []
    for line in iter(stdout.readline, ""):
        if not line:
            break
        out_buf.append(line)
        try:
            print(line.rstrip())
        except Exception:
            print(line.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore").rstrip())
        sys.stdout.flush()
    rc = stdout.channel.recv_exit_status()
    err = stderr.read().decode("utf-8", errors="ignore")
    return rc, "".join(out_buf), err


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[ssh] connecting {USER}@{HOST}:{PORT} ...")
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

    # 1. git pull
    rc, _, err = run(ssh, f"cd {PROJECT_DIR} && git fetch origin master && git reset --hard origin/master")
    if rc != 0:
        print(f"[FAIL] git pull failed: {err}")
        sys.exit(1)

    # 2. docker compose build --no-cache h5-web
    rc, _, err = run(ssh, f"cd {PROJECT_DIR} && docker compose build --no-cache h5-web", timeout=1800)
    if rc != 0:
        print(f"[FAIL] docker build failed: {err}")
        sys.exit(2)

    # 3. docker compose up -d h5-web
    rc, _, err = run(ssh, f"cd {PROJECT_DIR} && docker compose up -d h5-web", timeout=300)
    if rc != 0:
        print(f"[FAIL] docker up failed: {err}")
        sys.exit(3)

    # 4. wait for container ready
    print("[wait] sleeping 30s for h5-web ready ...")
    time.sleep(30)

    # 5. run automation tests
    run_tests(ssh)

    ssh.close()


def run_tests(ssh):
    """8 项服务器端非UI自动化测试。"""
    results = []

    def t(name, cmd, check):
        rc, out, err = run(ssh, cmd)
        ok = check(rc, out, err)
        status = "PASS" if ok else "FAIL"
        results.append((name, status, out[:500]))
        print(f"\n[{status}] {name}")

    # gateway 强制 http→https，使用 https 域名访问；容器名后缀为 -h5（不是 -h5-web）
    base = f"https://{HOST}{BASE_URL_PATH}"
    h5_ct = f"{DEPLOY_ID}-h5"

    t(
        "T1 H5 main page 200 (积分主页)",
        f"curl -s -o /dev/null -w '%{{http_code}}' -L {base}/points",
        lambda rc, out, err: out.strip().endswith("200"),
    )

    t(
        "T2 积分商城列表页 200",
        f"curl -s -o /dev/null -w '%{{http_code}}' -L {base}/points/mall",
        lambda rc, out, err: out.strip().endswith("200"),
    )

    t(
        "T3 积分商品详情页 200",
        f"curl -s -o /dev/null -w '%{{http_code}}' -L '{base}/points/product-detail?id=1'",
        lambda rc, out, err: out.strip().endswith("200"),
    )

    t(
        "T4 积分明细聚合页 200",
        f"curl -s -o /dev/null -w '%{{http_code}}' -L {base}/points/detail",
        lambda rc, out, err: out.strip().endswith("200"),
    )

    t(
        "T5 旧版积分流水页 200",
        f"curl -s -o /dev/null -w '%{{http_code}}' -L {base}/points/records",
        lambda rc, out, err: out.strip().endswith("200"),
    )

    t(
        "T6 兑换记录页 200",
        f"curl -s -o /dev/null -w '%{{http_code}}' -L {base}/points/exchange-records",
        lambda rc, out, err: out.strip().endswith("200"),
    )

    t(
        "T7 h5 容器内构建产物含天蓝色 #0EA5E9（积分主页）",
        f"docker exec {h5_ct} sh -c "
        f"\"grep -c '0EA5E9' /app/.next/server/app/points/page.js 2>/dev/null || echo 0\"",
        lambda rc, out, err: any(line.strip().isdigit() and int(line.strip()) > 0 for line in out.splitlines()),
    )

    t(
        "T8 h5 容器内积分主页已不含老绿色 (#1B5E20 / #2E7D32 / #C8E6C9)",
        f"docker exec {h5_ct} sh -c "
        f"\"grep -cE '1B5E20|2E7D32|C8E6C9' /app/.next/server/app/points/page.js 2>/dev/null || echo 0\"",
        lambda rc, out, err: any(line.strip() == "0" for line in out.splitlines()),
    )

    t(
        "T9 h5 容器内积分商城页含 banner 天蓝色 #0EA5E9",
        f"docker exec {h5_ct} sh -c "
        f"\"grep -c '0EA5E9' /app/.next/server/app/points/mall/page.js 2>/dev/null || echo 0\"",
        lambda rc, out, err: any(line.strip().isdigit() and int(line.strip()) > 0 for line in out.splitlines()),
    )

    t(
        "T10 h5 容器内积分商品详情页 CTA 含 #0EA5E9",
        f"docker exec {h5_ct} sh -c "
        f"\"grep -c '0EA5E9' /app/.next/server/app/points/product-detail/page.js 2>/dev/null || echo 0\"",
        lambda rc, out, err: any(line.strip().isdigit() and int(line.strip()) > 0 for line in out.splitlines()),
    )

    print("\n=== 测试结果汇总 ===")
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    for name, status, snippet in results:
        print(f" {status}  {name}")
    print(f"\nTotal: {len(results)}  PASS: {passed}  FAIL: {failed}")
    if failed > 0:
        sys.exit(10)


if __name__ == "__main__":
    main()
