import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
CONF_PATH = f"/home/ubuntu/gateway/conf.d/{PROJECT_ID}.conf"
PROJECT_DIR = f"/home/ubuntu/{PROJECT_ID}"

stdin, stdout, stderr = ssh.exec_command(f"cat {CONF_PATH}")
current_conf = stdout.read().decode()
print("Current conf:")
print(current_conf)

static_location = f"""
# Static file downloads (miniprogram zips, APKs, etc.)
location ~ ^/autodev/{PROJECT_ID}/(.*\\.(zip|apk|tar\\.gz|pdf|docx|png|jpg|jpeg|gif|svg|ico))$ {{
    alias {PROJECT_DIR}/$1;
    add_header Content-Disposition 'attachment';
    add_header Cache-Control 'no-cache';
}}
"""

if "Static file downloads" in current_conf:
    print("\nStatic file location already exists in config!")
else:
    insert_before = f"location /autodev/{PROJECT_ID}/api"
    if insert_before in current_conf:
        new_conf = current_conf.replace(insert_before, static_location + "\n" + insert_before)
        print("\nNew conf (with static file serving):")
        print(new_conf)

        stdin, stdout, stderr = ssh.exec_command(f"cp {CONF_PATH} {CONF_PATH}.bak.static")
        stdout.read()

        sftp = ssh.open_sftp()
        with sftp.open(CONF_PATH, "w") as f:
            f.write(new_conf)
        sftp.close()
        print("\nConfig written successfully.")

        stdin, stdout, stderr = ssh.exec_command("docker exec gateway nginx -t")
        out = stderr.read().decode() + stdout.read().decode()
        print(f"\nnginx -t: {out}")

        if "test is successful" in out:
            stdin, stdout, stderr = ssh.exec_command("docker exec gateway nginx -s reload")
            stdout.read()
            stderr.read()
            print("nginx reloaded!")
        else:
            print("Config test FAILED, restoring backup...")
            stdin, stdout, stderr = ssh.exec_command(f"cp {CONF_PATH}.bak.static {CONF_PATH}")
            stdout.read()
            stdin, stdout, stderr = ssh.exec_command("docker exec gateway nginx -s reload")
            stdout.read()
    else:
        print(f"\nCould not find insertion point: {insert_before}")

ssh.close()
