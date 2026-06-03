"""把 db 容器连接到 backend 所在的网络。不重启 db 以免丢数据。"""
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def sh(client, cmd, t=120):
    print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=t)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    if out:
        print(out[-2000:])
    if err:
        print("ERR:", err[-1000:])
    return out, err


client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PWD, timeout=30)

print("==== 把 db 容器加入 backend 网络（共享，不影响 db 业务） ====")
sh(client, f"docker network connect --alias {DEPLOY_ID}-db --alias db {DEPLOY_ID}-network {DEPLOY_ID}-db 2>&1 | tail -5; echo done")

print("\n==== 验证 backend 可以解析 db hostname ====")
sh(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"import socket; print(socket.gethostbyname('{DEPLOY_ID}-db'))\" 2>&1 || true")

print("\n==== 重启 backend ====")
sh(client, f"docker restart {DEPLOY_ID}-backend")
time.sleep(15)

print("\n==== 检查 backend 状态 ====")
sh(client, f"docker ps --filter name={DEPLOY_ID}-backend --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")
sh(client, f"docker logs --tail 20 {DEPLOY_ID}-backend 2>&1 | tail -25")

print("\n==== Smoke ====")
sh(client, f"curl -sk -o /dev/null -w 'health=%{{http_code}}\\n' {BASE_URL}/api/health")
sh(client, f"curl -sk -o /dev/null -w 'sr_status_unauth=%{{http_code}}\\n' {BASE_URL}/api/safety-rope/status")
sh(client, f"curl -sk -o /tmp/cp.json -w 'sr_check_phone=%{{http_code}}\\n' '{BASE_URL}/api/safety-rope/contacts/check-phone?phone=13700001111'")
sh(client, "cat /tmp/cp.json; echo")

client.close()
