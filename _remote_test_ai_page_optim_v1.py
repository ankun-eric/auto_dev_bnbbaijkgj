"""[PRD-AI-PAGE-OPTIM-V1 2026-05-21] 远程容器内执行 pytest + HTTP 烟测"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def sh(cli, cmd, t=240):
    si, so, se = cli.exec_command(cmd, timeout=t)
    return (
        so.read().decode(errors="replace"),
        se.read().decode(errors="replace"),
        so.channel.recv_exit_status(),
    )


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=60)
    try:
        # 1. pytest（容器内）
        print("======== pytest test_ai_page_optim_v1_20260521 ========")
        o, e, c = sh(
            cli,
            f"docker exec {DEPLOY_ID}-backend sh -c 'cd /app && python -m pytest tests/test_ai_page_optim_v1_20260521.py --tb=short -q 2>&1'",
            t=180,
        )
        print(o[-4000:])
        print("---stderr---", e[-1000:])
        print("[exit]", c)

        # 2. HTTP 烟测
        print("\n======== HTTP smoke ========")
        urls = [
            f"{BASE_URL}/",
            f"{BASE_URL}/health-profile",
            f"{BASE_URL}/admin/",
            f"{BASE_URL}/admin/system/seed-import",
            f"{BASE_URL}/api/openapi.json",
        ]
        for u in urls:
            o, _, _ = sh(
                cli,
                f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 10 '{u}'",
            )
            print(f"{u}: {o.strip()}")

        # 3. 检查新 API：/api/admin/seed-packs（需要 admin 令牌，未带应返回 401/403）
        print("\n======== API: /api/admin/seed-packs（无 token） ========")
        o, _, _ = sh(
            cli,
            f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 10 '{BASE_URL}/api/admin/seed-packs'",
        )
        print(f"/api/admin/seed-packs (no auth): {o.strip()} (期望 401/403)")

        # 4. 检查路由是否挂载（grep openapi.json）
        print("\n======== openapi.json 包含 seed-packs ========")
        o, _, _ = sh(
            cli,
            f"curl -s --max-time 15 '{BASE_URL}/api/openapi.json' | python3 -c 'import sys,json;d=json.load(sys.stdin);print([p for p in d.get(\"paths\",{{}}).keys() if \"seed-packs\" in p])'",
            t=60,
        )
        print(o.strip())

        # 5. 检查 旧路由 /health-archive 在 H5 是否已 404
        print("\n======== H5 旧 /health-archive 路由 ========")
        o, _, _ = sh(
            cli,
            f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 10 '{BASE_URL}/health-archive'",
        )
        print(f"/health-archive: {o.strip()} (期望 404)")

    finally:
        cli.close()


if __name__ == "__main__":
    main()
