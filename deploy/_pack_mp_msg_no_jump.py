"""[PRD-MSG-NOTICE-NO-JUMP-V1] 打包小程序 zip 并上传到 gateway-nginx 容器内 /data/static/apk/。

服务器静态目录路径：
  - 浏览器下载地址：{BASE}/downloads/<filename>.zip
  - gateway 容器内对应：/data/static/apk/<filename>.zip

执行：python deploy/_pack_mp_msg_no_jump.py
"""

import os
import sys
import time
import secrets
import zipfile
import paramiko

sys.path.insert(0, "deploy")
from _sshlib import HOST, PORT, USER, PASSWORD, DEPLOY_ID

BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
LOCAL_MP_DIR = "miniprogram"
EXCLUDE = {
    "node_modules",
    ".git",
    "__pycache__",
    ".DS_Store",
    "miniprogram_npm",
}


def make_zip(out_path, root_dir):
    n = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for cur, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE]
            for f in files:
                if f in EXCLUDE:
                    continue
                fp = os.path.join(cur, f)
                rel = os.path.relpath(fp, root_dir)
                zf.write(fp, arcname=rel)
                n += 1
    return n


def upload_into_container(local_zip, remote_name):
    """先上传到 /home/ubuntu/tmp/，再 docker cp 进 gateway-nginx 容器"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    try:
        sftp = c.open_sftp()
        try:
            sftp.mkdir("/home/ubuntu/tmp")
        except IOError:
            pass
        tmp_remote = f"/home/ubuntu/tmp/{remote_name}"
        print(f"  SFTP 上传 {local_zip} -> {tmp_remote}")
        sftp.put(local_zip, tmp_remote)
        sftp.close()

        # docker cp 进容器
        target = f"gateway-nginx:/data/static/apk/{remote_name}"
        cmd = f"docker cp {tmp_remote} {target} && rm -f {tmp_remote}"
        print(f"  执行: {cmd}")
        stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
        out = stdout.read().decode()
        err = stderr.read().decode()
        code = stdout.channel.recv_exit_status()
        if code != 0:
            raise RuntimeError(f"docker cp 失败: code={code}\n{out}\n{err}")
        return code
    finally:
        c.close()


def verify_download(url):
    import urllib.request
    import ssl
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            return r.status, r.headers.get("Content-Length")
    except Exception as e:
        return None, str(e)


def main():
    ts = time.strftime("%Y%m%d_%H%M%S")
    rnd = secrets.token_hex(2)
    fname = f"miniprogram_msg_no_jump_{ts}_{rnd}.zip"
    local_zip = os.path.abspath(fname)

    print(f"[1/3] 打包 {LOCAL_MP_DIR} → {fname}")
    n_files = make_zip(local_zip, LOCAL_MP_DIR)
    size = os.path.getsize(local_zip)
    print(f"     文件数 {n_files}，大小 {size/1024:.1f} KB")

    print(f"[2/3] 上传到服务器 gateway-nginx 容器 /data/static/apk/{fname}")
    upload_into_container(local_zip, fname)

    download_url = f"{BASE_URL}/downloads/{fname}"
    print(f"[3/3] 验证下载链接 {download_url}")
    status, info = verify_download(download_url)
    print(f"     HTTP {status} (Content-Length={info})")

    # 清理本地 zip
    try:
        os.remove(local_zip)
    except Exception:
        pass

    if status == 200:
        print("\n=== SUCCESS ===")
        print(f"DOWNLOAD_URL: {download_url}")
        # 写入文件名供后续手册引用
        with open("deploy/_mp_msg_no_jump_zipname.txt", "w", encoding="utf-8") as f:
            f.write(fname + "\n")
            f.write(download_url + "\n")
        sys.exit(0)
    else:
        print("\n=== FAILED ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
