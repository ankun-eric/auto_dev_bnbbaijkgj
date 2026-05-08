"""[BUG-FIX-REBUY-V1] 服务器测试脚本：容器内 pytest（按需 pip install）+ H5 chunks 验证。"""
from __future__ import annotations

import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def exec_cmd(client, cmd, timeout=600):
    print(f"[exec] {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-4000:])
    if err and code != 0:
        print("[stderr]", err[-2000:])
    return code, out, err


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30)

    backend = f"{DEPLOY_ID}-backend"

    # 列容器名（确认 h5 容器名）
    print("=== docker ps（含项目所有容器） ===")
    exec_cmd(client, f"docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}' | grep {DEPLOY_ID}", timeout=20)

    # 安装 pytest + httpx + aiosqlite + pytest-asyncio（如果缺失）
    print("\n=== 容器内 pip install pytest ===")
    exec_cmd(
        client,
        f"docker exec {backend} sh -lc 'pip install -i https://mirrors.cloud.tencent.com/pypi/simple --trusted-host mirrors.cloud.tencent.com pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -20'",
        timeout=420,
    )

    # 跑 reorder pytest
    print("\n=== 容器内 pytest test_reorder_bug_fix_v1.py ===")
    rc, pytest_out, _ = exec_cmd(
        client,
        f"docker exec {backend} sh -lc 'cd /app && python -m pytest tests/test_reorder_bug_fix_v1.py -v 2>&1' | tail -150",
        timeout=240,
    )

    # H5 chunks token 验证（用通配符找容器）
    print("\n=== H5 容器 chunks token 验证 ===")
    exec_cmd(
        client,
        f"H5C=$(docker ps --format '{{{{.Names}}}}' | grep {DEPLOY_ID} | grep -E 'h5' | head -1) && "
        f"echo \"Container: $H5C\" && "
        f"docker exec $H5C sh -lc 'grep -rl \"/reorder\" /app/.next/static/chunks/ 2>/dev/null | head -5 || echo NOT_FOUND_reorder'",
        timeout=30,
    )
    exec_cmd(
        client,
        f"H5C=$(docker ps --format '{{{{.Names}}}}' | grep {DEPLOY_ID} | grep -E 'h5' | head -1) && "
        f"docker exec $H5C sh -lc 'grep -rl \"from_rebuy\" /app/.next/static/chunks/ 2>/dev/null | head -5 || echo NOT_FOUND_from_rebuy'",
        timeout=30,
    )

    # 检查 reorder 接口在 OpenAPI 中
    print("\n=== /api/orders/unified/{order_id}/reorder 在 OpenAPI 中存在 ===")
    exec_cmd(
        client,
        f"curl -k -s 'https://{HOST}/autodev/{DEPLOY_ID}/api/openapi.json' | python3 -c 'import sys,json; d=json.load(sys.stdin); paths=list(d[\"paths\"].keys()); print(\"reorder?\", any(\"reorder\" in p for p in paths)); [print(p) for p in paths if \"reorder\" in p]'",
        timeout=30,
    )

    client.close()

    # 解析 pytest 结果
    import re
    m_passed = re.search(r"(\d+)\s+passed", pytest_out or "")
    m_failed = re.search(r"(\d+)\s+failed", pytest_out or "")
    n_passed = int(m_passed.group(1)) if m_passed else 0
    n_failed = int(m_failed.group(1)) if m_failed else 0
    print(f"\n=== pytest summary: {n_passed} passed, {n_failed} failed ===")
    return 0 if (n_passed >= 8 and n_failed == 0) else 2


if __name__ == "__main__":
    sys.exit(main())
