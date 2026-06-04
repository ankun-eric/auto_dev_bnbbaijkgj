"""Step 3: place zip into the host-mounted /home/ubuntu/{DEPLOY_ID}/static/miniprogram/
which is mounted into gateway container as /data/static/miniprogram/.
nginx alias: /autodev/{DEPLOY_ID}/miniprogram/ -> /data/static/miniprogram/
"""
import os
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ZIP_NAME = "miniprogram_20260526_144955_7480.zip"
LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), ZIP_NAME)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30,
          allow_agent=False, look_for_keys=False)


def run(cmd):
    print(f"\n$ {cmd[:240]}", flush=True)
    _, o, e = c.exec_command(cmd)
    rc = o.channel.recv_exit_status()
    so = o.read().decode().strip()
    se = e.read().decode().strip()
    if so: print(so[-3000:])
    if se: print(f"[stderr] {se[-1500:]}")
    return rc, so, se


HOST_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/miniprogram"
DEST = f"{HOST_DIR}/{ZIP_NAME}"

# 删除之前误放到 static 根目录的文件
run(f"rm -f /home/ubuntu/{DEPLOY_ID}/static/{ZIP_NAME}")

# 上传到目标目录
sftp = c.open_sftp()
tmp_remote = f"/home/ubuntu/{ZIP_NAME}"
print(f"\nSFTP put {LOCAL} -> {tmp_remote}")
sftp.put(LOCAL, tmp_remote)
sftp.close()

run(f"mkdir -p {HOST_DIR}")
run(f"cp {tmp_remote} {DEST}")
run(f"chmod 644 {DEST}")
run(f"ls -la {DEST}")
run(f"docker exec gateway ls -la /data/static/miniprogram/{ZIP_NAME}")

url = f"https://{HOST}/autodev/{DEPLOY_ID}/miniprogram/{ZIP_NAME}"
print(f"\n验证: {url}")
run(f"curl -ks -o /dev/null -w 'HTTP %{{http_code}} size=%{{size_download}}\\n' '{url}'")
run(f"curl -ksI '{url}' | head -12")

run(f"rm -f {tmp_remote}")

c.close()
print(f"\n=== FINAL ===")
print(f"FILENAME: {ZIP_NAME}")
print(f"URL:      {url}")
