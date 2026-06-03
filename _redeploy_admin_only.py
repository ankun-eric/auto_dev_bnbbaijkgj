"""Quick redeploy admin-web only after adding 3px row left bar."""
import paramiko, posixpath, os, time
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

def run(c, cmd, timeout=900):
    print(f"\n$ {cmd[:200]}")
    si, so, se = c.exec_command(cmd, timeout=timeout)
    out = so.read().decode("utf-8", "replace")
    err = se.read().decode("utf-8", "replace")
    code = so.channel.recv_exit_status()
    if out: print(out[-3000:])
    if err: print("[err]", err[-1500:])
    print(f"[exit {code}]")
    return code, out, err

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=60)
sftp = c.open_sftp()
sftp.put(
    "admin-web/src/app/(admin)/home-safety/page.tsx",
    f"{PROJECT_DIR}/admin-web/src/app/(admin)/home-safety/page.tsx",
)
sftp.close()
print("uploaded")
run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build admin-web 2>&1 | tail -60", timeout=900)
run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate admin-web 2>&1 | tail -20", timeout=180)
time.sleep(8)
run(c, f"docker logs {DEPLOY_ID}-admin --tail 30 2>&1 | tail -30")
c.close()
