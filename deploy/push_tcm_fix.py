"""推送 BUG① 的 tcm.py 二次修复 + 重启 backend。"""
import os, io, tarfile, time, paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(c, cmd, timeout=900):
    print(f"\n$ {cmd[:200]}")
    si, so, se = c.exec_command(cmd, timeout=timeout)
    out = so.read().decode("utf-8", "replace")
    err = se.read().decode("utf-8", "replace")
    code = so.channel.recv_exit_status()
    if out: print(out[-2000:])
    if err: print("[err]", err[-1000:])
    print(f"[exit {code}]")
    return code


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=60)

buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as tar:
    tar.add(os.path.join(LOCAL, "backend/app/api/tcm.py"), arcname="backend/app/api/tcm.py")
buf.seek(0)
sftp = c.open_sftp()
remote = f"/tmp/{DEPLOY_ID}-tcm-fix.tar.gz"
with sftp.open(remote, "wb") as f:
    f.write(buf.getvalue())
sftp.close()

run(c, f"cd {PROJECT_DIR} && tar -xzf {remote} && rm -f {remote}")
run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -10")
run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate backend 2>&1 | tail -10", timeout=180)
time.sleep(10)
run(c, "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend grep -n 'BUG \\xe2\\x91\\xa0 \\xe5\\x85\\xb3\\xe9\\x94\\xae\\xe4\\xbf\\xae\\xe5\\xa4\\x8d' /app/app/api/tcm.py || true")
c.close()
print("DONE")
