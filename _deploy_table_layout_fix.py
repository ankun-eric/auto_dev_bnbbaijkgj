#!/usr/bin/env python3
"""
[2026-05-05] 部署 admin-web 表格布局 Bug 修复
打包 admin-web 源码 -> 上传 -> 在服务器内 docker 中 npm install + build -> 复制到运行容器 -> 重启
"""
import os
import sys
import time
import tarfile
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_ADMIN_WEB = r"C:\auto_output\bnbbaijkgj\admin-web"
TAR_NAME = "admin_web_table_layout_fix.tar.gz"
LOCAL_TAR = rf"C:\auto_output\bnbbaijkgj\{TAR_NAME}"
CONTAINER_NAME = f"{DEPLOY_ID}-admin"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    return client


def run_cmd(client, cmd, timeout=600):
    print(f"\n>>> {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out[-3000:] if len(out) > 3000 else out)
    if err.strip():
        print(f"STDERR: {err[-2000:] if len(err) > 2000 else err}")
    return out, err


def pack_src():
    print(f"=== Packing admin-web source files ===")
    excludes = {"node_modules", ".next", ".git", "__pycache__", ".env.local", "out"}
    if os.path.exists(LOCAL_TAR):
        os.remove(LOCAL_TAR)
    count = 0
    with tarfile.open(LOCAL_TAR, "w:gz") as tar:
        for root, dirs, files in os.walk(LOCAL_ADMIN_WEB):
            dirs[:] = [d for d in dirs if d not in excludes]
            for file in files:
                if file == "tsconfig.tsbuildinfo":
                    continue
                fp = os.path.join(root, file)
                arc = os.path.relpath(fp, LOCAL_ADMIN_WEB)
                tar.add(fp, arcname=arc)
                count += 1
    size = os.path.getsize(LOCAL_TAR)
    print(f"Packed {count} files, {size/1024:.1f} KB -> {LOCAL_TAR}")


def upload(client, local_path, remote_path):
    print(f"\n=== Uploading {os.path.basename(local_path)} ===")
    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    print("Upload OK")


def main():
    pack_src()

    client = ssh_connect()
    print(f"Connected to {HOST}")

    remote_tar = f"/tmp/{TAR_NAME}"
    upload(client, LOCAL_TAR, remote_tar)

    build_dir = f"/tmp/admin_web_build_layout_{int(time.time())}"
    print("\n=== Prepare build directory ===")
    run_cmd(client, f"rm -rf {build_dir} && mkdir -p {build_dir} && cd {build_dir} && tar -xzf {remote_tar}")

    print("\n=== Run npm install + build inside Docker container ===")
    build_cmd = (
        f"docker run --rm "
        f"-v {build_dir}:/app -w /app "
        f"-e NEXT_PUBLIC_API_URL=/autodev/{DEPLOY_ID}/api "
        f"-e NEXT_PUBLIC_BASE_PATH=/autodev/{DEPLOY_ID}/admin "
        f"node:18-alpine sh -c "
        f"\"npm config set registry https://registry.npmmirror.com && "
        f"npm install --legacy-peer-deps --no-audit --no-fund && "
        f"NEXT_PUBLIC_API_URL=/autodev/{DEPLOY_ID}/api "
        f"NEXT_PUBLIC_BASE_PATH=/autodev/{DEPLOY_ID}/admin "
        f"npm run build\" 2>&1"
    )
    out, err = run_cmd(client, build_cmd, timeout=900)

    if "Compiled successfully" not in out and "error" in out.lower() and "warning" not in out[-200:].lower():
        print("\n*** Build appears to have failed; checking output... ***")
    
    out, _ = run_cmd(client, f"ls -la {build_dir}/.next/standalone/ 2>&1 | head -20")
    if "No such file" in out:
        print("ERROR: standalone build output missing")
        client.close()
        sys.exit(1)

    print("\n=== Pack built output ===")
    run_cmd(client, f"cd {build_dir} && tar -czf /tmp/next_built_layout.tar.gz .next/standalone .next/static public 2>&1 || tar -czf /tmp/next_built_layout.tar.gz .next/standalone .next/static 2>&1")

    print("\n=== Copy build into running admin container ===")
    run_cmd(client, f"docker cp /tmp/next_built_layout.tar.gz {CONTAINER_NAME}:/tmp/")
    
    extract_cmd = (
        f'docker exec {CONTAINER_NAME} sh -c "'
        f'cd /tmp && rm -rf .next public && tar -xzf next_built_layout.tar.gz && '
        f'cp -r .next/standalone/. /app/ && '
        f'rm -rf /app/.next/static && cp -r .next/static /app/.next/static && '
        f'(test -d public && rm -rf /app/public && cp -r public /app/public || true) && '
        f'echo DONE_EXTRACT" 2>&1'
    )
    run_cmd(client, extract_cmd)

    print("\n=== Restart admin container ===")
    run_cmd(client, f"docker restart {CONTAINER_NAME}")
    time.sleep(15)

    print("\n=== Container status ===")
    run_cmd(client, f"docker ps --filter name={CONTAINER_NAME} --format '{{{{.Names}}}}|{{{{.Status}}}}'")
    run_cmd(client, f"docker logs --tail=20 {CONTAINER_NAME} 2>&1")

    print("\n=== Health check ===")
    out1, _ = run_cmd(client, f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/admin/ --max-time 30")
    out2, _ = run_cmd(client, f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/admin/login --max-time 30")
    out3, _ = run_cmd(client, f"curl -s -o /dev/null -w '%{{http_code}}' {BASE_URL}/admin/merchant/stores --max-time 30")
    print(f"Admin /:    {out1.strip()}")
    print(f"Admin /login: {out2.strip()}")
    print(f"Admin /merchant/stores: {out3.strip()}")

    print("\n=== Cleanup ===")
    run_cmd(client, f"rm -rf {build_dir} /tmp/next_built_layout.tar.gz {remote_tar}")

    client.close()
    print("\n=== Deployment complete ===")
    print(f"Visit: {BASE_URL}/admin/merchant/stores")


if __name__ == "__main__":
    main()
