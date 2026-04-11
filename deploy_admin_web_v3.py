#!/usr/bin/env python3
"""
Deploy admin-web by:
1. Extracting node_modules from the existing builder image 
2. Building Next.js with the new source files
3. Replacing the running container's built files
"""
import paramiko
import os
import tarfile
import time

HOST = "newbb.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
SERVER_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ADMIN_WEB = r"C:\auto_output\bnbbaijkgj\admin-web"
TAR_NAME = "admin_web_src.tar.gz"
LOCAL_TAR = rf"C:\auto_output\bnbbaijkgj\{TAR_NAME}"
CONTAINER_NAME = f"{DEPLOY_ID}-admin"
IMAGE_NAME = f"{DEPLOY_ID}-admin-web"


def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    return client


def run_cmd(client, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out)
    if err:
        print(f"STDERR: {err[:2000]}")
    return out, err


def pack_src_only():
    print(f"\n=== Packing admin-web source files ===")
    excludes = {"node_modules", ".next", ".git", "__pycache__", ".env.local", "tsconfig.tsbuildinfo"}
    
    with tarfile.open(LOCAL_TAR, "w:gz") as tar:
        for root, dirs, files in os.walk(LOCAL_ADMIN_WEB):
            dirs[:] = [d for d in dirs if d not in excludes]
            for file in files:
                if file == "tsconfig.tsbuildinfo":
                    continue
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, LOCAL_ADMIN_WEB)
                tar.add(filepath, arcname=arcname)
    
    size = os.path.getsize(LOCAL_TAR)
    print(f"Created {LOCAL_TAR} ({size/1024:.1f} KB)")


def upload_file(client, local_path, remote_path):
    print(f"\n=== Uploading {os.path.basename(local_path)} ===")
    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    print("Upload complete.")


def main():
    pack_src_only()
    
    print(f"\n=== Connecting to {HOST} ===")
    client = ssh_connect()
    print("Connected!")
    
    # Check existing images
    print("\n=== Check existing Docker images ===")
    out, _ = run_cmd(client, f"docker images | grep {DEPLOY_ID[:8]}")
    
    # Upload source tar
    remote_tar = f"/tmp/{TAR_NAME}"
    upload_file(client, LOCAL_TAR, remote_tar)
    
    # Create a build script on server that:
    # 1. Uses node:18-alpine to build with npm install
    # 2. Uses npm mirror to speed up install
    build_script = f"""#!/bin/sh
set -e
BUILD_DIR=/tmp/admin_web_build_{DEPLOY_ID[:8]}
rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR
cd $BUILD_DIR
tar -xzf {remote_tar}

# Run npm install and build in a docker container using npm mirror
docker run --rm \\
  -v $BUILD_DIR:/app \\
  -w /app \\
  -e NEXT_PUBLIC_API_URL=/autodev/{DEPLOY_ID}/api \\
  -e NEXT_PUBLIC_BASE_PATH=/autodev/{DEPLOY_ID}/admin \\
  node:18-alpine sh -c "
    npm config set registry https://registry.npmmirror.com &&
    npm install --legacy-peer-deps &&
    NEXT_PUBLIC_API_URL=/autodev/{DEPLOY_ID}/api NEXT_PUBLIC_BASE_PATH=/autodev/{DEPLOY_ID}/admin npm run build
  "

echo "Build complete!"
ls -la $BUILD_DIR/.next/
"""
    
    print("\n=== Write build script to server ===")
    run_cmd(client, f"cat > /tmp/build_admin.sh << 'BUILDEOF'\n{build_script}\nBUILDEOF")
    run_cmd(client, "chmod +x /tmp/build_admin.sh")
    
    print("\n=== Run build (this may take a while) ===")
    out, err = run_cmd(client, "sh /tmp/build_admin.sh 2>&1", timeout=600)
    
    if "Build complete!" not in out:
        print("\nERROR: Build may have failed, checking...")
        build_dir = f"/tmp/admin_web_build_{DEPLOY_ID[:8]}"
        run_cmd(client, f"ls {build_dir}/.next/ 2>&1")
    
    # Now package the standalone output and copy into running container
    build_dir = f"/tmp/admin_web_build_{DEPLOY_ID[:8]}"
    print("\n=== Package built output ===")
    run_cmd(client, 
        f"cd {build_dir} && tar -czf /tmp/next_built.tar.gz .next/standalone .next/static public 2>&1")
    
    # Stop the current container, replace files, restart
    print("\n=== Update container with new build ===")
    # Copy built files into container
    run_cmd(client, f"docker cp /tmp/next_built.tar.gz {CONTAINER_NAME}:/tmp/")
    
    # Extract into container's /app
    run_cmd(client, 
        f'docker exec {CONTAINER_NAME} sh -c "cd /app && tar -xzf /tmp/next_built.tar.gz --strip-components=2 .next/standalone/ 2>&1 || true"')
    
    # Better approach: extract standalone to /app directly
    run_cmd(client,
        f'docker exec {CONTAINER_NAME} sh -c "cd /tmp && tar -xzf /tmp/next_built.tar.gz && cp -r .next/standalone/. /app/ && cp -r .next/static /app/.next/static && cp -r public /app/public 2>&1 || true"')
    
    print("\n=== Restart container ===")
    run_cmd(client, f"docker restart {CONTAINER_NAME}")
    time.sleep(15)
    
    print("\n=== Verify container ===")
    run_cmd(client, f"docker ps | grep {DEPLOY_ID[:8]}")
    run_cmd(client, f"docker logs {CONTAINER_NAME} --tail=20")
    
    # Health check
    base_url = f"https://{HOST}/autodev/{DEPLOY_ID}"
    print("\n=== Health check ===")
    out1, _ = run_cmd(client, f"curl -s -o /dev/null -w '%{{http_code}}' {base_url}/admin/ --max-time 30")
    out2, _ = run_cmd(client, f"curl -s -o /dev/null -w '%{{http_code}}' {base_url}/api/health --max-time 30")
    
    print(f"\nAdmin: {out1.strip()}")
    print(f"API: {out2.strip()}")
    
    # Cleanup
    run_cmd(client, f"rm -rf /tmp/admin_web_build_{DEPLOY_ID[:8]} /tmp/next_built.tar.gz /tmp/{TAR_NAME}")
    
    client.close()
    print("\n=== Deployment complete ===")


if __name__ == "__main__":
    main()
