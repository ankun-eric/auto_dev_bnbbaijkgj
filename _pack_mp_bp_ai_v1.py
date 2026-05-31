"""[PRD-BP-AI-EXPLAIN-V1 2026-05-31] 打包小程序 zip 并上传到服务器静态目录。

服务器静态目录策略：参考 user_docs 中其它 zip/apk 的下载链接形式，
zip 通过 gateway-nginx 暴露在项目基础 URL 下：
  https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/{file}.zip
"""
import os
import sys
import time
import zipfile
import secrets
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
ROOT = os.path.dirname(os.path.abspath(__file__))
MP_DIR = os.path.join(ROOT, "miniprogram")

ts = time.strftime("%Y%m%d_%H%M%S")
suffix = secrets.token_hex(2)
ZIP_NAME = f"miniprogram_{ts}_{suffix}.zip"
ZIP_LOCAL = os.path.join(ROOT, ZIP_NAME)

EXCLUDE_DIRS = {"node_modules", ".git", "dist", ".idea"}
EXCLUDE_EXT = {".log"}


def pack():
    print(f">>> Packing miniprogram to {ZIP_NAME} ...")
    with zipfile.ZipFile(ZIP_LOCAL, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(MP_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if os.path.splitext(f)[1].lower() in EXCLUDE_EXT:
                    continue
                full = os.path.join(root, f)
                arc = os.path.relpath(full, MP_DIR)
                zf.write(full, arcname=arc)
    print(f"    size = {os.path.getsize(ZIP_LOCAL)//1024} KB")


def upload():
    """通过后端容器的 /app/uploads（绑定 volume）发布 zip，
    访问 URL 由 nginx 的 location /uploads/ → backend:/uploads/ 反向代理。"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=30, look_for_keys=False, allow_agent=False)

    def run(cmd, timeout=60):
        print(f"$ {cmd}")
        si, so, se = ssh.exec_command(cmd, timeout=timeout)
        o = so.read().decode("utf-8", errors="ignore")
        e = se.read().decode("utf-8", errors="ignore")
        if o: print(o.rstrip())
        if e: print("STDERR:", e.rstrip())
        return so.channel.recv_exit_status(), o, e

    backend_ctn = f"{DEPLOY_ID}-backend"
    remote_tmp = f"/tmp/{ZIP_NAME}"
    sftp = ssh.open_sftp()
    sftp.put(ZIP_LOCAL, remote_tmp)
    sftp.close()
    print(f"  uploaded host -> {remote_tmp}")

    # docker cp 进后端容器 /app/uploads/
    run(f"docker cp {remote_tmp} {backend_ctn}:/app/uploads/{ZIP_NAME}")
    run(f"rm -f {remote_tmp}")
    run(f"docker exec {backend_ctn} ls -la /app/uploads/{ZIP_NAME}")
    ssh.close()


def verify():
    url = f"{BASE_URL}/uploads/{ZIP_NAME}"
    # 远程 curl 验证可达
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASS, timeout=15, look_for_keys=False, allow_agent=False)
    si, so, se = cli.exec_command(
        f"curl -fsS -o /dev/null -w '%{{http_code}}' '{url}'", timeout=30
    )
    code = so.read().decode().strip()
    print(f"Download URL: {url}")
    print(f"HTTP: {code}")
    cli.close()
    return url, code


if __name__ == "__main__":
    pack()
    upload()
    url, code = verify()
    print(f"\n>>> ZIP URL: {url}  (HTTP={code})")
    # 保存供后续手册引用
    with open(os.path.join(ROOT, "_mp_bp_ai_url.txt"), "w", encoding="utf-8") as f:
        f.write(f"{url}\n")
