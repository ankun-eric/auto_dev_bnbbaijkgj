"""
重新拉取最新代码并重建 h5。上一次 git fetch 因网速慢失败但被 tail 吞掉 exit code，
导致服务器上的代码并未真正更新（仍停留在 835daa1）。本次：
- 用 -c http.lowSpeedLimit=0 -c http.postBuffer=...  避免 "too slow" 中断
- 在失败时重试最多 5 次
- 然后再次 reset --hard origin/master
- 重建 h5-web
"""
import paramiko, sys, time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
H5_CONTAINER = f"{DEPLOY_ID}-h5"
TARGET_COMMIT_PREFIX = "915887b4"


def run(client, cmd, timeout=600, label=None):
    label = label or cmd[:80]
    print(f"\n>>> {label}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode(errors="ignore")
    err = stderr.read().decode(errors="ignore")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out.rstrip())
    if err:
        print("STDERR:", err.rstrip())
    print(f"--- exit={rc}")
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PWD, timeout=30,
                   look_for_keys=False, allow_agent=False)
    try:
        # 关闭 git 的速度阈值检测，避免国内连 GitHub 时 "too slow" 中断
        # 调小 depth 加快下载
        fetch_cmd = (
            f"cd {PROJ_DIR} && "
            f"git -c http.lowSpeedLimit=0 -c http.lowSpeedTime=600 "
            f"-c http.postBuffer=524288000 "
            f"fetch origin master --depth 30 --no-tags --progress 2>&1 | tail -5"
        )

        ok = False
        for attempt in range(1, 6):
            print(f"\n========= fetch attempt {attempt}/5 =========")
            rc, out, _ = run(client, fetch_cmd, timeout=300, label=f"git fetch (attempt {attempt})")
            # check actual remote head
            rc2, head, _ = run(client, f"cd {PROJ_DIR} && git rev-parse origin/master | cut -c1-8",
                               label="check origin/master after fetch")
            head = head.strip()
            print(f"origin/master is now: {head}")
            if head.startswith(TARGET_COMMIT_PREFIX):
                ok = True
                break
            time.sleep(8)

        if not ok:
            print("ERROR: 多次重试后仍未拉到目标 commit, 终止。")
            return 1

        run(client, f"cd {PROJ_DIR} && git reset --hard origin/master && git log -1 --oneline",
            label="reset --hard + show head")

        # 直接看本次修复文件中的关键字是否真的进入工作区
        run(client, f"cd {PROJ_DIR} && grep -c 'BUGFIX-AI-HOME-5ITEMS-V1' h5-web/src/app/\\(ai-chat\\)/ai-home/page.tsx 2>/dev/null || true",
            label="grep BUGFIX marker in page.tsx")
        run(client, f"cd {PROJ_DIR} && grep -c '权益升级' h5-web/src/components/ai-chat/Sidebar.tsx 2>/dev/null || true",
            label="grep 权益升级 in Sidebar.tsx")

        # 重建 h5-web 容器
        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1 | tail -25",
            timeout=1500, label="rebuild h5-web --no-cache")

        run(client, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1 | tail -15",
            label="up -d h5-web")

        # 等待启动
        for i in range(18):
            rc, out, _ = run(client,
                             f"docker inspect -f '{{{{.State.Status}}}} {{{{.State.Health.Status}}}}' {H5_CONTAINER} 2>/dev/null",
                             label=f"h5 status check {i+1}/18")
            s = out.strip()
            if "healthy" in s or ("running" in s and i >= 4):
                break
            time.sleep(5)

        # 找 gateway 容器名
        rc, out, _ = run(client, "docker ps --format '{{.Names}}' | grep -i 'gateway\\|nginx-gw\\|gw-nginx\\|^gateway' || docker ps --format '{{.Names}}'",
                         label="find gateway container")

        # 验证 H5 容器里有新代码标记
        run(client, (
            f"docker exec {H5_CONTAINER} sh -c '"
            f"echo === marker count ===; "
            f"grep -roh \"BUGFIX-AI-HOME-5ITEMS-V1\" .next 2>/dev/null | wc -l; "
            f"echo === 权益升级 vs 权益管理与升级 ===; "
            f"grep -rh \"权益升级\\|权益管理与升级\" .next 2>/dev/null | head -3; "
            f"echo === plus-circle icon ===; "
            f"grep -rho \"ai-home-more-icon-plus-circle\" .next 2>/dev/null | head -3; "
            f"echo === 新角标 (should be 0) ===; "
            f"grep -rho \"ai-home-more-menu-item-新角标\" .next 2>/dev/null | wc -l'"),
            label="verify code in h5 container")

        # 外部访问
        url_base = f"https://{HOST}/autodev/{DEPLOY_ID}"
        for p in ["/", "/ai-home/", "/ai-home/medication-reminder/"]:
            run(client, f"curl -sS -L -o /dev/null -w 'HTTP %{{http_code}} %{{size_download}}B in %{{time_total}}s URL=%{{url_effective}}\\n' '{url_base}{p}' --max-time 20",
                label=f"external GET {p}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
