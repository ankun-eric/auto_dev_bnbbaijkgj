"""仅完成 H5 build + reload nginx + smoke test（接续 v2_bugfix 部署）"""
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def sh(client, cmd, timeout=180, quiet=False):
    if not quiet:
        print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    rc = stdout.channel.recv_exit_status()
    if out and not quiet:
        print(out[-3000:])
    if err and not quiet:
        print("STDERR:", err[-1500:])
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)

    print("[1] 启动 H5 build (后台 setsid)")
    # 用 setsid + 单独的 transport channel：完全脱离 SSH session
    chan = client.get_transport().open_session()
    chan.exec_command(
        f"setsid bash -c 'cd {PROJ} && docker compose -f docker-compose.prod.yml build --no-cache h5-web > /tmp/h5_build_bugfix.log 2>&1' &"
    )
    chan.close()
    time.sleep(3)
    rc, out, _ = sh(client, "pgrep -af 'docker.*build.*h5-web' | head -3; ls -la /tmp/h5_build_bugfix.log", timeout=10)

    print("[2] 轮询 H5 build 状态")
    for i in range(80):  # 最长 20 分钟
        time.sleep(15)
        rc, out, _ = sh(
            client,
            "if pgrep -f 'docker.*build.*h5-web' >/dev/null; then echo BUILDING; else echo BUILD_DONE; fi; tail -2 /tmp/h5_build_bugfix.log",
            timeout=15, quiet=True
        )
        elapsed = (i + 1) * 15
        if "BUILD_DONE" in out:
            print(f"  H5 build done after {elapsed}s")
            print("  tail:", out[-500:].replace("\n", " | "))
            break
        if i % 4 == 0:
            print(f"  ...{elapsed}s, tail: {out[-300:].replace(chr(10), ' | ')}")
    else:
        print("  WARN: H5 build still running after 20min, continue anyway")

    print("\n[3] up h5-web")
    sh(client, f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate h5-web", timeout=180)

    print("\n[4] Reload nginx")
    time.sleep(8)
    sh(client, "docker exec gateway-nginx nginx -t && docker exec gateway-nginx nginx -s reload || true", timeout=30)

    print("\n[5] Smoke test")
    sh(client, f"curl -sk -o /dev/null -w 'health=%{{http_code}}\\n' {BASE_URL}/api/health")
    sh(client, f"curl -sk -o /dev/null -w 'sr_status_unauth=%{{http_code}}\\n' {BASE_URL}/api/safety-rope/status")
    sh(client, f"curl -sk -o /dev/null -w 'sr_check_phone_unauth=%{{http_code}}\\n' '{BASE_URL}/api/safety-rope/contacts/check-phone?phone=13700001111'")
    sh(client, f"curl -sk -o /dev/null -w 'h5_safety_rope=%{{http_code}}\\n' {BASE_URL}/care-safety-rope")
    sh(client, f"curl -sk -o /dev/null -w 'h5_care_home=%{{http_code}}\\n' {BASE_URL}/care-home")
    sh(client, f"curl -sk -o /dev/null -w 'h5_care_sos=%{{http_code}}\\n' {BASE_URL}/care-ai-home/sos")

    print("\n[6] 检查后端容器日志（最近 50 行）")
    sh(client, f"docker logs --tail 50 {DEPLOY_ID}-backend 2>&1 | grep -iE 'error|safety|warning' | head -30", timeout=20)

    print("\n部署完成。")
    client.close()


if __name__ == "__main__":
    main()
