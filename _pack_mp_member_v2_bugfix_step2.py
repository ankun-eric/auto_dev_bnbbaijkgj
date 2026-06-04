"""Step 2: upload zip to gateway-mapped /data/static/miniprogram/
Use the existing zip generated in step 1.
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


# 找 gateway 容器并查看 /data/static 挂载
run("docker ps --format '{{.Names}}\t{{.Image}}' | grep -i gateway")
run("docker inspect gateway-nginx --format '{{range .Mounts}}{{.Source}}->{{.Destination}}{{println}}{{end}}' 2>/dev/null || docker inspect $(docker ps --format '{{.Names}}' | grep -i nginx | head -1) --format '{{range .Mounts}}{{.Source}}->{{.Destination}}{{println}}{{end}}'")

# /data/static/miniprogram/ 在 gateway-nginx 容器内 → 我们要找宿主机对应路径
# 上传到宿主 /home/ubuntu，然后 docker cp 到 gateway-nginx 容器，或 mv 到挂载源
run("docker exec gateway-nginx ls /data/static/miniprogram/ 2>/dev/null | head -10")

# 上传 zip 到宿主临时目录
sftp = c.open_sftp()
tmp_remote = f"/home/ubuntu/{ZIP_NAME}"
print(f"\nSFTP put {LOCAL} -> {tmp_remote}")
sftp.put(LOCAL, tmp_remote)
sftp.close()
run(f"ls -la {tmp_remote}")

# 方案 A: 直接 docker cp 到 gateway-nginx 容器 /data/static/miniprogram/
run(f"docker exec gateway ls -la /data/static/ 2>/dev/null")
run(f"docker exec gateway mkdir -p /data/static/miniprogram/")
run(f"docker cp {tmp_remote} gateway:/data/static/miniprogram/{ZIP_NAME}")
run(f"docker exec gateway ls -la /data/static/miniprogram/{ZIP_NAME}")
# Also try the host-mounted path if available
run(f"docker inspect gateway --format '{{{{range .Mounts}}}}{{{{.Source}}}}->{{{{.Destination}}}}{{{{println}}}}{{{{end}}}}'")

# 验证
url = f"https://{HOST}/autodev/{DEPLOY_ID}/miniprogram/{ZIP_NAME}"
print(f"\n验证: {url}")
run(f"curl -ks -o /dev/null -w 'HTTP %{{http_code}} size=%{{size_download}}\\n' '{url}'")
run(f"curl -ksI '{url}' | head -10")

# 清理临时
run(f"rm -f {tmp_remote}")

c.close()
print(f"\n=== FINAL ===")
print(f"FILENAME: {ZIP_NAME}")
print(f"URL:      {url}")
