import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Bangbang987", timeout=30)

deploy_id = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
apk_name = "bini_health_android-v20260410-142406-uqk2.apk"
conf_path = f"/home/ubuntu/gateway/conf.d/{deploy_id}.conf"

# Read existing conf
stdin, stdout, stderr = ssh.exec_command(f"cat {conf_path}")
existing_conf = stdout.read().decode()

# Check if APK location already exists
if "apk" not in existing_conf.lower() or ".apk" not in existing_conf:
    apk_location = f"""
# APK 下载
location ~ ^/autodev/{deploy_id}/(.*\\.apk)$ {{
    alias /home/ubuntu/{deploy_id}/$1;
    default_type application/vnd.android.package-archive;
    add_header Content-Disposition 'attachment';
}}
"""
    # Insert before the H5 catch-all location (which is "location /autodev/{deploy_id}/")
    # We need to add it before that block
    marker = f"# H5 用户端"
    if marker in existing_conf:
        new_conf = existing_conf.replace(marker, apk_location + "\n" + marker)
    else:
        new_conf = existing_conf + "\n" + apk_location

    # Write new conf
    cmd = f"cat > {conf_path} << 'NGINX_CONF_EOF'\n{new_conf}\nNGINX_CONF_EOF"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    err = stderr.read().decode()
    if exit_status != 0:
        print(f"Failed to write conf: {err}")
    else:
        print("Updated nginx conf with APK location block")

    # Now we need to add the volume mount for APK files
    # First, stop the container, recreate with additional mount
    # Actually, let's check if we can use a different approach - use docker cp or recreate
    # Simpler: just add a volume mount and recreate the container

    # Check current docker run command
    stdin, stdout, stderr = ssh.exec_command("docker inspect gateway-nginx --format '{{json .HostConfig.Binds}}'")
    binds = stdout.read().decode().strip()
    print(f"Current binds: {binds}")

    # Add the APK directory mount by recreating the container
    # First get the full container config
    stdin, stdout, stderr = ssh.exec_command("docker inspect gateway-nginx --format '{{json .Config.Image}}'")
    image = stdout.read().decode().strip().strip('"')
    print(f"Image: {image}")

    # Get network
    stdin, stdout, stderr = ssh.exec_command("docker inspect gateway-nginx --format '{{json .NetworkSettings.Networks}}'")
    networks = stdout.read().decode().strip()
    print(f"Networks: {networks}")

    # Stop and remove the current container, recreate with added mount
    cmds = [
        "docker stop gateway-nginx",
        "docker rm gateway-nginx",
        f"docker run -d --name gateway-nginx "
        f"--network 3b7b999d-e51c-4c0d-8f6e-baf90cd26857_default "
        f"--network 5cffe06b-41cb-4d63-902f-15b2fb8c7685_default "
        f"-p 80:80 -p 443:443 "
        f"-v /home/ubuntu/gateway/nginx.conf:/etc/nginx/nginx.conf:ro "
        f"-v /home/ubuntu/gateway/ssl:/etc/nginx/ssl:ro "
        f"-v /home/ubuntu/gateway/conf.d:/etc/nginx/conf.d:ro "
        f"-v /home/ubuntu/gateway/certbot-webroot:/var/www/certbot:ro "
        f"-v /home/ubuntu/{deploy_id}/static:/home/ubuntu/{deploy_id}/static:ro "
        f"-v /home/ubuntu/{deploy_id}:/home/ubuntu/{deploy_id}:ro "
        f"--restart unless-stopped "
        f"{image}",
    ]

    for cmd in cmds:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        if out:
            print(f"OUT: {out}")
        if err:
            print(f"ERR: {err}")
        print(f"Exit: {exit_status}")

    # Verify nginx is running
    import time
    time.sleep(3)
    stdin, stdout, stderr = ssh.exec_command("docker ps --filter name=gateway-nginx --format '{{.Status}}'")
    status = stdout.read().decode().strip()
    print(f"\nGateway status: {status}")

    # Test nginx config
    stdin, stdout, stderr = ssh.exec_command("docker exec gateway-nginx nginx -t")
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(f"Nginx test: {out} {err}")
else:
    print("APK location block already exists in conf")

ssh.close()
