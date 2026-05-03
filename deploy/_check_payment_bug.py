"""检查服务器上支付配置 Bug 的实际情况。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(client, cmd, timeout=60):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}")
    return out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    try:
        run(client, f"docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}' | grep {DID}")
        run(client, f"cd /home/ubuntu/{DID} && git log --oneline -3")

        # 检查 docker-compose 中的环境变量
        run(client, f"cd /home/ubuntu/{DID} && grep -i payment_config_encryption_key docker-compose.yml || echo '<未配置 PAYMENT_CONFIG_ENCRYPTION_KEY>'")

        # 检查后端容器内的环境变量
        run(client, f"docker exec {DID}-backend printenv | grep -i 'PAYMENT\\|PUBLIC_API' || echo '<容器内无 PAYMENT_* 环境变量>'")

        # 检查后端容器内 payment_channels 表是否存在 + 数据
        run(client, f"docker exec {DID}-db mysql -uroot -proot bini_health -e 'SELECT id, channel_code, channel_name, display_name, is_enabled, is_complete FROM payment_channels;' 2>&1 | head -20")

        # 检查后端容器是否能跑通 list 接口（不带 token 应该返 401，带错的也能看到响应结构）
        run(client, f"docker exec {DID}-backend curl -s -o /tmp/r.json -w '%{{http_code}}' http://localhost:8000/api/admin/payment-channels && echo && docker exec {DID}-backend cat /tmp/r.json | head -c 500")

        # 检查 nginx 网关能否到达
        run(client, f"curl -s -o /dev/null -w 'gateway %{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DID}/api/admin/payment-channels")

        # 检查后端最近日志（找异常）
        run(client, f"docker logs --tail 100 {DID}-backend 2>&1 | grep -i 'payment\\|crypto\\|encrypt\\|error\\|trace' | tail -30 || echo '<日志中无相关错误>'")
    finally:
        client.close()


if __name__ == "__main__":
    main()
