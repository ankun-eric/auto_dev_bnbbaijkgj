"""部署后 smoke 校验：检查关键路由可达 + 关键错误结构化字段。"""
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
REMOTE_HOST = "newbb.test.bangbangvip.com"
REMOTE_USER = "ubuntu"
REMOTE_PASS = "Newbang888"


def ssh(cmd, header=""):
    if header:
        print(f"\n=== {header} ===")
    print(f"[REMOTE] $ {cmd[:200]}")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASS, timeout=30)
    _, stdout, _ = client.exec_command(cmd, timeout=60, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    client.close()
    print(out[-3000:])
    print(f"[rc={rc}]")
    return rc, out


def main():
    # 1) 关键路由可达性
    routes = [
        ("h5_root", "/"),
        ("h5_login", "/login"),
        ("h5_orders", "/orders"),
        ("h5_unified_order_demo", "/unified-order/1"),
        ("api_health", "/api/health"),
        ("api_docs", "/api/docs"),
        ("api_appointment_no_auth", "/api/orders/unified/1/appointment"),
    ]
    cmds = "; ".join(
        f"curl -s -o /dev/null -w '{name}=%{{http_code}}\\n' {BASE_URL}{path}"
        for name, path in routes
    )
    ssh(cmds, header="A: route reachability")

    # 2) 验证 X-Client-Source 逻辑：未带 Token 也应返回 401/403 而非 500
    ssh(
        f"curl -s -X POST {BASE_URL}/api/orders/unified/1/appointment "
        f"-H 'Content-Type: application/json' "
        f"-H 'X-Client-Source: h5-customer' "
        f"-d '{{\"appointment_time\":\"2026-08-01T10:00:00\"}}' -w '\\nHTTP=%{{http_code}}\\n'",
        header="B: X-Client-Source header is accepted by API (no auth)",
    )

    # 3) 容器存活
    ssh(
        f"docker ps --filter 'name={DEPLOY_ID}' --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'",
        header="C: container status",
    )


if __name__ == "__main__":
    main()
