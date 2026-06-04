"""修复 backend 启动 + 完整冒烟测试"""
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

    print("[1] 检查容器状态")
    sh(client, f"docker ps -a --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

    print("\n[2] 先启动 db / redis 服务（不重启）")
    sh(client, f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d db redis", timeout=120)
    time.sleep(8)

    print("\n[3] 等待 db 健康")
    for i in range(20):
        time.sleep(3)
        rc, out, _ = sh(client, f"docker exec {DEPLOY_ID}-db mysqladmin ping -h localhost -uroot -ppassword 2>&1 | tail -1", timeout=10, quiet=True)
        if "alive" in out.lower():
            print(f"  ✓ db alive after {(i+1)*3}s")
            break
        if i % 3 == 0:
            print(f"  ...{(i+1)*3}s waiting db: {out.strip()[:200]}")

    print("\n[4] 重启 backend")
    sh(client, f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate backend", timeout=120)
    time.sleep(15)

    print("\n[5] 检查 backend 日志")
    sh(client, f"docker logs --tail 30 {DEPLOY_ID}-backend 2>&1 | tail -40", timeout=20)

    print("\n[6] 检查容器状态")
    sh(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

    print("\n[7] Smoke test")
    sh(client, f"curl -sk -o /dev/null -w 'health=%{{http_code}}\\n' {BASE_URL}/api/health")
    sh(client, f"curl -sk -o /dev/null -w 'sr_status_unauth=%{{http_code}}\\n' {BASE_URL}/api/safety-rope/status")
    rc, out, _ = sh(client, f"curl -sk -o /tmp/cp.json -w 'sr_check_phone=%{{http_code}}\\n' '{BASE_URL}/api/safety-rope/contacts/check-phone?phone=13700001111'")
    sh(client, "cat /tmp/cp.json 2>/dev/null; echo")
    sh(client, f"curl -skL -o /dev/null -w 'h5_safety_rope=%{{http_code}}\\n' {BASE_URL}/care-safety-rope")
    sh(client, f"curl -skL -o /dev/null -w 'h5_care_home=%{{http_code}}\\n' {BASE_URL}/care-home")
    sh(client, f"curl -skL -o /dev/null -w 'h5_care_sos=%{{http_code}}\\n' {BASE_URL}/care-ai-home/sos")

    client.close()


if __name__ == "__main__":
    main()
