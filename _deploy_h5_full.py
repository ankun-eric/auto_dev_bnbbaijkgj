#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包 h5-web Next.js standalone 产物并部署到远程容器。"""
import os
import sys
import time
import tarfile
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
H5_CONTAINER = f"{PROJECT_ID}-h5"

ROOT = os.path.dirname(os.path.abspath(__file__))
H5_DIR = os.path.join(ROOT, "h5-web")
STANDALONE = os.path.join(H5_DIR, ".next", "standalone")
STATIC = os.path.join(H5_DIR, ".next", "static")
PUBLIC = os.path.join(H5_DIR, "public")
TAR_LOCAL = os.path.join(ROOT, "_h5_standalone.tar.gz")
TAR_REMOTE = f"/tmp/_h5_standalone_{PROJECT_ID}.tar.gz"


def pack():
    print(">>> Packing standalone bundle ...")
    if os.path.exists(TAR_LOCAL):
        os.remove(TAR_LOCAL)
    with tarfile.open(TAR_LOCAL, "w:gz") as tf:
        # standalone 根目录（含 server.js, .next/server, node_modules, package.json）
        for name in os.listdir(STANDALONE):
            tf.add(os.path.join(STANDALONE, name), arcname=name)
        # 把 static 放到 standalone/.next/static
        tf.add(STATIC, arcname=".next/static")
        # public 资源
        if os.path.isdir(PUBLIC):
            tf.add(PUBLIC, arcname="public")
    print(f"    tar created: {TAR_LOCAL} ({os.path.getsize(TAR_LOCAL)//1024} KB)")


def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=20)

    print(">>> Uploading to remote ...")
    sftp = ssh.open_sftp()
    sftp.put(TAR_LOCAL, TAR_REMOTE)
    sftp.close()

    def run(cmd, timeout=300):
        print(f"$ {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="ignore")
        err = stderr.read().decode("utf-8", errors="ignore")
        if out:
            print(out.rstrip())
        if err:
            print("STDERR:", err.rstrip())
        return out, err

    # 用 docker cp + tar 在容器内解压（覆盖）
    run(f"docker cp {TAR_REMOTE} {H5_CONTAINER}:/tmp/h5.tar.gz")
    # 解压到 /app（覆盖）
    run(f"docker exec {H5_CONTAINER} sh -c 'cd /app && tar xzf /tmp/h5.tar.gz && rm -f /tmp/h5.tar.gz'")
    # 清理远程 tar
    run(f"rm -f {TAR_REMOTE}")
    # 验证文件
    run(f"docker exec {H5_CONTAINER} ls /app")
    run(f"docker exec {H5_CONTAINER} ls /app/.next | head -5")
    # 重启容器
    print(">>> Restart h5 container ...")
    run(f"docker restart {H5_CONTAINER}")
    # 等待几秒
    print(">>> Waiting 6s ...")
    time.sleep(6)
    run(f"docker logs --tail 15 {H5_CONTAINER}")
    ssh.close()


if __name__ == "__main__":
    pack()
    deploy()
    print(">>> H5 deploy DONE")
