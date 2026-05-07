"""Bug401 admin-web 重建并部署"""
import paramiko, sys, time

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR=f"/home/ubuntu/{DID}"

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, timeout=1500):
    print(f"\n>>> {cmd}", flush=True)
    chan=c.get_transport().open_session(); chan.settimeout(timeout); chan.get_pty(); chan.exec_command(cmd)
    last=time.time()
    out_buf=b""
    while True:
        if chan.recv_ready():
            d=chan.recv(65535); out_buf+=d
            try: print(d.decode("utf-8",errors="ignore"),end="",flush=True)
            except: pass
            last=time.time()
        if chan.exit_status_ready() and not chan.recv_ready():
            break
        if time.time()-last>timeout:
            print("\n[TIMEOUT]"); break
        time.sleep(0.4)
    rc=chan.recv_exit_status()
    print(f"\n[rc={rc}]", flush=True)
    return rc, out_buf.decode("utf-8",errors="ignore")

# 1. 确认当前 commit
run(f"cd {PROJ_DIR} && git log -1 --oneline")

# 2. 重建并启动 admin-web 容器
print("\n========== 开始重建 admin-web 容器 ==========")
run(f"cd {PROJ_DIR} && docker compose build admin-web 2>&1 | tail -50", timeout=1800)

# 3. 重启容器
run(f"cd {PROJ_DIR} && docker compose up -d admin-web 2>&1 | tail -10")

# 4. 等待容器启动
time.sleep(3)
run(f"docker ps --filter name={DID}-admin --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

# 5. 验证页面可访问
url_orders = f"https://newbb.test.bangbangvip.com/autodev/{DID}/admin/product-system/orders"
url_dashboard = f"https://newbb.test.bangbangvip.com/autodev/{DID}/admin/product-system/orders/dashboard"

run(f"curl -s -o /dev/null -w 'orders=%{{http_code}}\\n' '{url_orders}'")
run(f"curl -s -o /dev/null -w 'dashboard=%{{http_code}}\\n' '{url_dashboard}'")

# 6. 抓取响应体确认不再是 Gateway OK
run(f"curl -s '{url_orders}' | head -c 500")
print()
run(f"curl -s '{url_dashboard}' | head -c 500")

c.close()
