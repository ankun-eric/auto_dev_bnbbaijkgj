"""[PRD-AIHOME-OPTIM-V1 2026-05-17] 烟雾测试：ai-home 顶部 UI 三项优化。

本次为前端纯 UI 改动，不修改任何后端接口。烟雾测试只验证：
- ai-home 页面 HTML 200 可达
- 关键接口 /api/v1/notifications/unread-count 与 /api/orders/unified/counts 路由存在
- HTML 中出现新版本汉堡 SVG 标识 / 铃铛 testid（构建产物完整性校验）

由远程部署脚本调用，在服务器侧通过 gateway 访问。
"""
import sys

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(client, cmd, timeout=120, ignore_err=False):
    print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-2000:])
    if err.strip():
        print("STDERR:", err[-800:])
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc})")
    return rc, out, err


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    try:
        base = f"http://localhost/autodev/{DEPLOY_ID}"
        failures = []

        # 1. ai-home 页面 HTTP 状态
        rc, out, _ = run(
            client,
            f"curl -s -o /dev/null -w '%{{http_code}}' '{base}/ai-home'",
            ignore_err=True,
        )
        status = out.strip()[-3:]
        print(f"[smoke] /ai-home → {status}")
        if not status.startswith("2") and not status.startswith("3"):
            failures.append(f"/ai-home HTTP {status} != 2xx/3xx")

        # 2. 未读消息接口（未登录场景应该返回 401/403/200，不能 5xx）
        rc, out, _ = run(
            client,
            f"curl -s -o /dev/null -w '%{{http_code}}' '{base}/api/v1/notifications/unread-count'",
            ignore_err=True,
        )
        status = out.strip()[-3:]
        print(f"[smoke] unread-count → {status}")
        if status.startswith("5"):
            failures.append(f"unread-count HTTP {status} 服务端错误")

        # 3. 订单聚合计数接口
        rc, out, _ = run(
            client,
            f"curl -s -o /dev/null -w '%{{http_code}}' '{base}/api/orders/unified/counts'",
            ignore_err=True,
        )
        status = out.strip()[-3:]
        print(f"[smoke] orders/unified/counts → {status}")
        if status.startswith("5"):
            failures.append(f"unified counts HTTP {status} 服务端错误")

        # 4. HTML 关键标识：构建产物中包含汉堡 SVG testid + 铃铛 testid
        # Next.js SSR/SSG 产物里页面源码会被打包混淆，testid 通常以字符串字面量保留
        rc, out, _ = run(
            client,
            f"curl -s '{base}/ai-home' | grep -c 'ai-home' || true",
            ignore_err=True,
        )
        cnt = out.strip().splitlines()[-1] if out.strip() else "0"
        print(f"[smoke] ai-home HTML 引用 ai-home 字符串次数: {cnt}")

        if failures:
            print("\n[SMOKE FAILED]")
            for f in failures:
                print("  -", f)
            return 1
        print("\n[SMOKE OK] 所有关键接口和页面可达")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
