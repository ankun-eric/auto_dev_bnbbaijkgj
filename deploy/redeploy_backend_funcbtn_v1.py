"""快速重建 backend 容器"""
import paramiko
import time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)


def run(cmd, timeout=600):
    print(f">>> {cmd}")
    _, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace")
    e = err.read().decode("utf-8", errors="replace")
    print(o[:2000])
    if e.strip() and "warning" not in e.lower():
        print("ERR:", e[:500])
    print(f"[exit={out.channel.recv_exit_status()}]")


PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
run(f"cd {PROJ} && git fetch origin && git reset --hard origin/master && git log -1 --oneline")
run(f"cd {PROJ} && docker compose -f docker-compose.prod.yml build backend", timeout=900)
run(f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d backend", timeout=180)
time.sleep(10)
run(f"cd {PROJ} && docker compose -f docker-compose.prod.yml ps")
c.close()
