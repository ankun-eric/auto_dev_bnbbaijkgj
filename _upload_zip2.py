import paramiko, os
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ZIP_NAME = "miniprogram_20260525_114327_948f.zip"
LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), ZIP_NAME)
# 正确的 host 路径（gateway 容器的 /data/static 映射到此）
HOST_STATIC = f"/home/ubuntu/{DEPLOY_ID}/static/miniprogram"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(cmd):
    print(f"$ {cmd}")
    _, o, e = c.exec_command(cmd)
    so = o.read().decode().strip(); se = e.read().decode().strip()
    if so: print(so)
    if se: print(f"[stderr] {se}")


run(f"ls {HOST_STATIC} | head -5")
run(f"mkdir -p {HOST_STATIC}")

# 删之前误传位置的（可选）
run(f"sudo rm -f /data/static/miniprogram/{ZIP_NAME}")

sftp = c.open_sftp()
sftp.put(LOCAL, f"{HOST_STATIC}/{ZIP_NAME}")
sftp.close()
run(f"chmod 644 {HOST_STATIC}/{ZIP_NAME}")
run(f"ls -la {HOST_STATIC}/{ZIP_NAME}")

url = f"https://{HOST}/autodev/{DEPLOY_ID}/miniprogram/{ZIP_NAME}"
print(f"\nVerify: {url}")
run(f"curl -s -o /dev/null -w 'HTTP %{{http_code}} size=%{{size_download}}\\n' '{url}'")

c.close()
print(f"\nDOWNLOAD URL: {url}")
