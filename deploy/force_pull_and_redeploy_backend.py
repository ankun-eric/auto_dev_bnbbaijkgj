import paramiko
import time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(cmd, timeout=900):
    print(f">>> {cmd}")
    _, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace")
    e = err.read().decode("utf-8", errors="replace")
    print(o[:2500])
    code = out.channel.recv_exit_status()
    if code != 0 and e.strip():
        print(f"ERR(exit={code}):", e[:500])
    return code


# 用 sudo + 直接 fetch 和 reset master
run(f"cd {PROJ} && sudo -n git fetch origin master 2>&1 | head -5 || git fetch origin master 2>&1 | head -5")
run(f"cd {PROJ} && git reset --hard origin/master 2>&1 | head -10")
run(f"cd {PROJ} && git log -1 --oneline")
run(f"cd {PROJ} && grep -c coalesce backend/app/api/function_button.py")

# 重建 backend 强制不用 cache
run(f"cd {PROJ} && docker compose -f docker-compose.prod.yml build --no-cache backend", timeout=900)
run(f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d backend", timeout=180)
time.sleep(8)
run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend grep -c coalesce /app/app/api/function_button.py")
c.close()
