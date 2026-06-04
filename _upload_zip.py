import paramiko, os
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ZIP_NAME = "miniprogram_20260525_114327_948f.zip"
LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), ZIP_NAME)
REMOTE_STATIC = f"/home/ubuntu/gateway/static/{DEPLOY_ID}/miniprogram/{ZIP_NAME}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(cmd):
    print(f"$ {cmd}")
    _, o, e = c.exec_command(cmd)
    rc = o.channel.recv_exit_status()
    so = o.read().decode().strip()
    se = e.read().decode().strip()
    if so: print(so)
    if se: print(f"[stderr] {se}")
    return rc, so, se


# 先看 gateway 配置中 /miniprogram/ 实际指向哪个目录
run(f"sudo grep -A 3 'miniprogram' /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf | head -20")

# 用 docker 容器名上传方式：上传到一个可被 gateway 读到的位置
# 根据上面 conf 输出确认实际目录
# 先 mkdir 试 alias 路径 /data/static/miniprogram/
run("sudo mkdir -p /data/static/miniprogram/")
run("sudo chmod 755 /data/static/miniprogram/")

print(f"Uploading {LOCAL} -> ubuntu home then sudo move")
sftp = c.open_sftp()
tmp_remote = f"/home/ubuntu/{ZIP_NAME}"
sftp.put(LOCAL, tmp_remote)
sftp.close()
run(f"sudo mv {tmp_remote} /data/static/miniprogram/{ZIP_NAME}")
run(f"sudo chmod 644 /data/static/miniprogram/{ZIP_NAME}")
run(f"ls -la /data/static/miniprogram/{ZIP_NAME}")

# 验证 HTTPS 下载
url = f"https://{HOST}/autodev/{DEPLOY_ID}/miniprogram/{ZIP_NAME}"
print(f"\nVerify: {url}")
run(f"curl -s -o /dev/null -w 'HTTP %{{http_code}} size=%{{size_download}}\\n' '{url}'")
run(f"curl -sI '{url}' | head -10")

c.close()
print(f"\nDOWNLOAD URL: {url}")
