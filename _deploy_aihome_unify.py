import paramiko, sys, time, os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"

FILES = [
    "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
    "h5-web/src/app/care-ai-home/page.tsx",
    "h5-web/src/components/ai-chat/MoreMenu.tsx",
]

def run(cli, cmd, timeout=1800):
    print(f"\n$ {cmd[:120]}", flush=True)
    chan = cli.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    buf = b""
    try:
        while True:
            if chan.recv_ready():
                buf += chan.recv(65536)
            if chan.exit_status_ready() and not chan.recv_ready():
                break
            time.sleep(0.3)
        while chan.recv_ready():
            buf += chan.recv(65536)
    except Exception as e:
        print("[timeout/err]", e, flush=True)
    rc = chan.recv_exit_status()
    out = buf.decode("utf-8", "ignore")
    if out.strip():
        print(out[-4000:], flush=True)
    print(f"[rc={rc}]", flush=True)
    return rc, out

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)
print("connected", flush=True)

# 1. SFTP upload changed files
sftp = cli.open_sftp()
for f in FILES:
    local = os.path.join(r"C:\auto_output\bnbbaijkgj", f.replace("/", os.sep))
    remote = f"{PROJ}/{f}"
    print(f"upload {f}", flush=True)
    sftp.put(local, remote)
sftp.close()
print("upload done", flush=True)

# 2. rebuild h5-web only
run(cli, f"cd {PROJ} && docker compose -f docker-compose.yml build h5-web 2>&1 | tail -25", timeout=2400)
run(cli, f"cd {PROJ} && docker compose -f docker-compose.yml up -d h5-web 2>&1 | tail -10", timeout=300)

# 3. wait & status
time.sleep(8)
run(cli, f"docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID}", timeout=60)
run(cli, "docker ps --format '{{.Names}}' | grep -i gateway", timeout=60)
run(cli, f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>/dev/null; echo netok", timeout=60)

cli.close()
print("\nDEPLOY DONE", flush=True)
