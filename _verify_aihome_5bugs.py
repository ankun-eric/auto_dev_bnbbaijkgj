"""验证 5 项 Bug 修复已生效。"""
import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
H5 = f"{DEPLOY_ID}-h5"


def run(client, cmd, label=None, timeout=120):
    print(f"\n>>> {label or cmd[:80]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="ignore")
    err = stderr.read().decode(errors="ignore")
    rc = stdout.channel.recv_exit_status()
    if out: print(out.rstrip())
    if err: print("STDERR:", err.rstrip())
    print(f"--- exit={rc}")
    return rc, out


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30,
              look_for_keys=False, allow_agent=False)
    try:
        # 容器状态
        run(c, f"docker ps --filter name={H5} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'",
            label="h5 ps")
        run(c, f"docker logs --tail 30 {H5}", label="h5 logs tail")

        # 在容器内 grep
        # 用 -- 隔离避免 '(' 被 shell 截断；先 cd .next 再 grep
        commands = [
            ("BUGFIX marker", f"docker exec {H5} sh -c 'cd /app && grep -rho \"BUGFIX-AI-HOME-5ITEMS-V1\" .next 2>/dev/null | wc -l'"),
            ("ai-home-more-icon-plus-circle", f"docker exec {H5} sh -c 'cd /app && grep -rho \"ai-home-more-icon-plus-circle\" .next 2>/dev/null | wc -l'"),
            ("权益升级 出现次数", f"docker exec {H5} sh -c 'cd /app && grep -rho \"权益升级\" .next 2>/dev/null | wc -l'"),
            ("权益管理与升级 出现次数(应为0)", f"docker exec {H5} sh -c 'cd /app && grep -rho \"权益管理与升级\" .next 2>/dev/null | wc -l'"),
            ("新角标 testid (应为0)", f"docker exec {H5} sh -c 'cd /app && grep -rho \"ai-home-more-menu-item-新角标\" .next 2>/dev/null | wc -l'"),
            ("medication-plans/today 引用(铃铛走新接口)", f"docker exec {H5} sh -c 'cd /app && grep -rho \"medication-plans/today\" .next 2>/dev/null | wc -l'"),
            ("medication-reminder/today 残留(老接口已不再用)", f"docker exec {H5} sh -c 'cd /app && grep -rho \"medication-reminder/today\" .next 2>/dev/null | wc -l'"),
        ]
        for label, cmd in commands:
            run(c, cmd, label=label)

        # 直连容器内部 nodejs 服务
        run(c, f"docker exec {H5} sh -c 'wget -qO- http://localhost:3000/ 2>/dev/null | head -c 400 || curl -sf http://localhost:3000/ | head -c 400'",
            label="internal probe / (first 400 chars)")

        # 外部 HTTPS 关键页面
        base = f"https://{HOST}/autodev/{DEPLOY_ID}"
        paths = ["/", "/ai-home/", "/ai-home/medication-reminder/",
                 "/api/health", "/login/"]
        for p in paths:
            run(c, f"curl -sS -L -o /dev/null -w 'HTTP %{{http_code}} %{{size_download}}B URL=%{{url_effective}} redirects=%{{num_redirects}}\\n' '{base}{p}' --max-time 20",
                label=f"GET {p}")

        # 检测 HTML 中是否含新代码标记（验证最终用户能拿到新版本）
        run(c, f"curl -sSL --max-time 20 '{base}/ai-home/' | grep -E 'ai-home-more-icon-plus-circle|ai-home-hamburger-icon' | head -5 || echo 'no marker found in HTML (could be in chunk)'",
            label="HTML markers")
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
