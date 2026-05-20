"""[PRD-QUESTIONNAIRE-DRAWER-V1] 远端兼容回归。"""
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
CTR = f"{DEPLOY_ID}-backend"


def run(cli, cmd, timeout=300):
    print(f"$ {cmd}")
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err:
        print("[stderr]", err)
    return code, out, err


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    # 跑新测试 + 老 questionnaire_v1 测试
    files = [
        "tests/test_questionnaire_drawer_v1_20260519.py",
        "tests/test_questionnaire_v1_20260519.py",
        "tests/test_health_self_check.py",
    ]
    files_arg = " ".join(files)
    code, out, _ = run(
        cli,
        f"docker exec {CTR} bash -lc "
        f"'cd /app && python -m pytest --ignore-glob=tests/test_aichat_capsule_v2.py {files_arg} -v --no-header 2>&1 | tail -n 100'",
        timeout=600,
    )
    # smoke: render-meta
    code2, out2, _ = run(
        cli,
        f"docker exec {DEPLOY_ID}-mysql mysql -uroot -p888888 bini_health "
        f"-Nse \"SELECT id FROM chat_function_buttons WHERE ai_function_type='questionnaire' "
        f"AND questionnaire_template_id IS NOT NULL ORDER BY id LIMIT 1\" 2>/dev/null",
    )
    btn = (out2 or "").strip().splitlines()[-1].strip() if out2 else ""
    if btn and btn.isdigit():
        run(
            cli,
            f"curl -sk -w '\\nHTTP=%{{http_code}}\\n' "
            f"'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/questionnaire/buttons/{btn}/render-meta' "
            f"| head -c 800",
        )

    cli.close()
    sys.exit(code)


if __name__ == "__main__":
    main()
