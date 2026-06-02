"""数字安全绳部署 step2：H5 build + 烟雾测试"""
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def sh(client, cmd, timeout=120):
    print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    try:
        out = stdout.read().decode("utf-8", "ignore")
        err = stderr.read().decode("utf-8", "ignore")
    except Exception:
        out, err = "", ""
    if out:
        print(out[-1500:])
    if err:
        print("STDERR:", err[-800:])
    return out


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)

    # 后台启动 h5 build
    sh(c, f"cd {PROJ} && nohup docker compose -f docker-compose.prod.yml build --no-cache h5-web > /tmp/h5_build.log 2>&1 < /dev/null & disown")
    time.sleep(2)

    # 轮询直到完成
    for i in range(50):
        time.sleep(15)
        out = sh(c, "pgrep -f 'compose.*build.*h5-web' | wc -l")
        if out.strip().startswith("0"):
            break
        print(f"  waiting build... ({i+1}/50)")

    # 查看 build log 末尾
    sh(c, "tail -30 /tmp/h5_build.log")

    # 起动 h5-web 容器
    sh(c, f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate h5-web")
    time.sleep(8)

    # 网关 reload
    sh(c, "docker exec gateway-nginx nginx -t && docker exec gateway-nginx nginx -s reload || true")
    time.sleep(2)

    # 烟雾测试
    sh(c, f"curl -sk -o /dev/null -w 'api_health=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DID}/api/health")
    sh(c, f"curl -sk -o /dev/null -w 'safety_status_401=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DID}/api/safety-rope/status")
    sh(c, f"curl -sk -o /dev/null -w 'safety_contacts_401=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DID}/api/safety-rope/contacts")
    sh(c, f"curl -sk -o /dev/null -w 'h5_root=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DID}/")
    sh(c, f"curl -sk -o /dev/null -w 'h5_safety_rope=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DID}/care-safety-rope")
    sh(c, f"curl -sk -o /dev/null -w 'h5_care_home=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DID}/care-home")

    # 检查后端日志
    sh(c, "docker logs --tail 30 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | grep -E 'safety_rope|ERROR|started' | tail -15")

    c.close()


if __name__ == "__main__":
    main()
