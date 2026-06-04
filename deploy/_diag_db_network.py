"""诊断 backend 容器是否可以解析 db 容器的 hostname + 网络归属"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"


def sh(client, cmd, t=60):
    print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=t)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    if out:
        print(out[-3000:])
    if err:
        print("ERR:", err[-1000:])


client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PWD, timeout=30)

# 1. 检查网络
sh(client, "docker network ls | grep 6b099")
sh(client, f"docker inspect {DEPLOY_ID}-backend --format '{{{{json .NetworkSettings.Networks}}}}' | python3 -m json.tool 2>/dev/null || docker inspect {DEPLOY_ID}-backend --format '{{{{json .NetworkSettings.Networks}}}}'")
sh(client, f"docker inspect {DEPLOY_ID}-db --format '{{{{json .NetworkSettings.Networks}}}}' | python3 -m json.tool 2>/dev/null || docker inspect {DEPLOY_ID}-db --format '{{{{json .NetworkSettings.Networks}}}}'")

# 2. 在 backend 容器里 ping db 容器
sh(client, f"docker exec {DEPLOY_ID}-backend python3 -c \"import socket; print(socket.gethostbyname('{DEPLOY_ID}-db'))\" 2>&1 || true")

# 3. 看 backend 的环境变量（数据库配置）
sh(client, f"docker exec {DEPLOY_ID}-backend env | grep -E 'DB_|DATABASE|MYSQL' || true")

# 4. 看 db 容器的环境变量（root 密码）
sh(client, f"docker exec {DEPLOY_ID}-db env | grep -iE 'mysql' || true")

# 5. docker-compose 配置
sh(client, f"cat {PROJ}/docker-compose.prod.yml | grep -A5 -iE 'backend|db|network' | head -80")

client.close()
