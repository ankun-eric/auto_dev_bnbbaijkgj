import paramiko, time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DID}"
import os
# 凭据从环境变量读取，避免将 token 写入仓库（GitHub push protection）
GIT_USER = os.environ.get("GIT_USER", "ankun-eric")
GIT_TOKEN = os.environ.get("GIT_TOKEN", "")
GIT_URL = f"https://{GIT_USER}:{GIT_TOKEN}@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, t=1200, label=None):
    if label:
        print(f"\n===== {label} =====")
    print(f"$ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = ""
    for line in iter(stdout.readline, ""):
        print(line, end="")
        out += line
    err = stderr.read().decode("utf-8","ignore")
    if err.strip():
        print("[stderr]", err[-3000:])
    return out + err

# 1. 拉取最新代码
run(f"cd {PROJ} && git remote set-url origin {GIT_URL} && timeout 60 git fetch origin master --no-tags 2>&1", label="git fetch")
run(f"cd {PROJ} && git reset --hard origin/master 2>&1 && git log -1 --oneline", label="git reset")

# 2. 生成 BUILD_COMMIT
run(f"cd {PROJ} && BC=$(git log -1 --format=%H) && echo \"BUILD_COMMIT=$BC\" && grep -q '^BUILD_COMMIT=' .env 2>/dev/null && sed -i \"s|^BUILD_COMMIT=.*|BUILD_COMMIT=$BC|\" .env || echo \"BUILD_COMMIT=$BC\" >> .env", label="BUILD_COMMIT")

# 3. 重新构建 backend 与 h5-web（--no-cache）
run(f"cd {PROJ} && docker compose -f docker-compose.prod.yml build --no-cache backend h5-web 2>&1", t=2400, label="build backend+h5")

# 4. 重启
run(f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d backend h5-web 2>&1", label="up")

# 5. 等待就绪
time.sleep=__import__("time").sleep
for i in range(20):
    o = run(f"docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DID}", label=None)
    if "Restarting" not in o:
        break
    __import__("time").sleep(5)

# 6. gateway 重连网络
run(f"docker network connect {DID}-network gateway-nginx 2>/dev/null || true", label="gateway network connect")
run("docker exec gateway-nginx nginx -s reload 2>&1 || true", label="gateway reload")

c.close()
print("\nDONE")
