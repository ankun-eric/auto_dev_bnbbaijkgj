"""[PRD-AI-PAGE-OPTIM-V1] 进一步烟测：follow redirect 看最终状态 + 装 pytest 跑测试"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"


def sh(cli, cmd, t=600):
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
        # follow redirect
        print("======== HTTP follow-redirect 最终状态 ========")
        urls = [
            ("/health-profile (新页面)", f"{BASE_URL}/health-profile"),
            ("/health-archive (旧页面，期望404)", f"{BASE_URL}/health-archive"),
            ("/admin/system/seed-import", f"{BASE_URL}/admin/system/seed-import"),
        ]
        for tag, u in urls:
            o, _, _ = sh(
                cli,
                f"curl -s -L -o /dev/null -w '%{{http_code}}' --max-time 15 '{u}'",
            )
            print(f"  {tag}: {o.strip()}")

        # 检查 backend 是否能跑 pytest（安装并跑）
        print("\n======== 容器内 pytest（在线 pip install） ========")
        o, e, c = sh(
            cli,
            f"docker exec {DEPLOY_ID}-backend sh -c 'pip install -q pytest pytest-asyncio 2>&1 | tail -3 && cd /app && python -m pytest tests/test_ai_page_optim_v1_20260521.py --tb=short -q 2>&1 | tail -30'",
            t=300,
        )
        print(o)
        print("[exit]", c)

        # 检查迁移 log
        print("\n======== backend 启动 log：是否跳过种子插入 ========")
        o, _, _ = sh(
            cli,
            f"docker logs --tail 200 {DEPLOY_ID}-backend 2>&1 | grep -E '(SKIP|种子|seed|TCM|tcm|migration|Migration)' | tail -30",
        )
        print(o or "(no matched log)")

        # 检查孤儿模板清理是否已执行
        print("\n======== 孤儿模板清理 ========")
        o, _, _ = sh(
            cli,
            f"docker exec {DEPLOY_ID}-backend sh -c 'cd /app && python -c \"import asyncio; from scripts.cleanup_tcm_orphan_template import cleanup_orphan_tcm_template; print(asyncio.run(cleanup_orphan_tcm_template()))\" 2>&1 | tail -20'",
            t=120,
        )
        print(o)
    finally:
        cli.close()


if __name__ == "__main__":
    main()
