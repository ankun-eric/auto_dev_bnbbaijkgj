import paramiko
import sys
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_TAR = r"C:\auto_output\bnbbaijkgj\_deploy_tmp\deploy.tar"

def run_ssh(ssh, cmd, timeout=600):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.strip()[-3000:] if len(out.strip()) > 3000 else out.strip())
    if err.strip():
        print(f"STDERR: {err.strip()[-2000:]}" if len(err.strip()) > 2000 else f"STDERR: {err.strip()}")
    print(f"Exit code: {exit_code}")
    return exit_code, out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print(f"Connecting to {HOST}...")
    ssh.connect(HOST, username=USER, password=PASS, timeout=30)
    print("Connected!")

    # Step 1: Upload tar
    print("\n=== Step 1: Upload tar file ===")
    sftp = ssh.open_sftp()
    run_ssh(ssh, f"mkdir -p {REMOTE_DIR}")
    remote_tar = f"{REMOTE_DIR}/deploy.tar"
    print(f"Uploading {LOCAL_TAR} -> {remote_tar} ...")
    sftp.put(LOCAL_TAR, remote_tar)
    print("Upload complete!")
    sftp.close()

    # Step 2: Extract
    print("\n=== Step 2: Extract tar ===")
    run_ssh(ssh, f"cd {REMOTE_DIR} && tar -xf deploy.tar && rm deploy.tar")

    # Step 3: Check for .env file and create if needed
    print("\n=== Step 3: Check .env file ===")
    ec, out, _ = run_ssh(ssh, f"test -f {REMOTE_DIR}/.env && echo 'EXISTS' || echo 'MISSING'")
    if "MISSING" in out:
        print("Creating default .env file...")
        run_ssh(ssh, f'touch {REMOTE_DIR}/.env')

    # Step 4: Docker compose down
    print("\n=== Step 4: Docker compose down ===")
    run_ssh(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml down --remove-orphans 2>&1", timeout=120)

    # Step 5: Docker compose build
    print("\n=== Step 5: Docker compose build (no-cache) ===")
    ec, out, err = run_ssh(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml build --no-cache 2>&1", timeout=600)
    if ec != 0:
        print(f"WARNING: Build exited with code {ec}")

    # Step 6: Docker compose up
    print("\n=== Step 6: Docker compose up -d ===")
    ec, out, err = run_ssh(ssh, f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=120)

    # Step 7: Wait for containers
    print("\n=== Step 7: Wait for containers to start ===")
    time.sleep(10)
    
    for i in range(12):
        ec, out, _ = run_ssh(ssh, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}'")
        if "healthy" in out.lower() or (out.count("Up") >= 3 and i >= 2):
            print("Containers are up!")
            break
        print(f"Waiting... ({(i+1)*10}s)")
        time.sleep(10)

    # Step 8: Connect gateway to network
    print("\n=== Step 8: Connect gateway to project network ===")
    run_ssh(ssh, f"docker network connect {DEPLOY_ID}-network gateway 2>&1 || true")

    # Step 9: Update gateway route config
    print("\n=== Step 9: Update gateway nginx route config ===")
    gateway_conf_content = open(r"C:\auto_output\bnbbaijkgj\gateway-routes.conf", "r").read()
    
    sftp = ssh.open_sftp()
    conf_remote_path = f"/etc/nginx/conf.d/{DEPLOY_ID}.conf"
    
    # Write to temp first, then move with sudo
    tmp_conf = f"/tmp/{DEPLOY_ID}.conf"
    with sftp.open(tmp_conf, "w") as f:
        f.write(gateway_conf_content)
    sftp.close()
    
    run_ssh(ssh, f"docker cp {tmp_conf} gateway:/etc/nginx/conf.d/{DEPLOY_ID}.conf")

    # Step 10: Test and reload nginx in gateway container
    print("\n=== Step 10: Test and reload nginx ===")
    ec, out, err = run_ssh(ssh, "docker exec gateway nginx -t 2>&1")
    if ec == 0 or "successful" in (out + err).lower():
        run_ssh(ssh, "docker exec gateway nginx -s reload 2>&1")
        print("Nginx reloaded successfully!")
    else:
        print(f"WARNING: nginx -t failed! Trying reload anyway...")
        run_ssh(ssh, "docker exec gateway nginx -s reload 2>&1")

    # Step 11: Final status check
    print("\n=== Step 11: Final deployment verification ===")
    run_ssh(ssh, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'")
    
    # Check container logs for errors
    print("\n--- Backend container recent logs ---")
    run_ssh(ssh, f"docker logs --tail 20 {DEPLOY_ID}-backend 2>&1")
    
    print("\n--- Admin container recent logs ---")
    run_ssh(ssh, f"docker logs --tail 10 {DEPLOY_ID}-admin 2>&1")
    
    print("\n--- H5 container recent logs ---")
    run_ssh(ssh, f"docker logs --tail 10 {DEPLOY_ID}-h5 2>&1")

    ssh.close()
    print("\n=== Deployment complete! ===")

if __name__ == "__main__":
    main()
