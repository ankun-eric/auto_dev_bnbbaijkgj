import paramiko

PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", 22, "ubuntu", PASS, timeout=30)

def sh(cmd, timeout=30):
    print("$", cmd)
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace").rstrip()
    err = stderr.read().decode(errors="replace").rstrip()
    if out:
        print(out)
    if err and "[sudo]" not in err:
        print("STDERR:", err)
    print()

S = f"echo '{PASS}' | sudo -S -p '' "
sh(S + f"docker exec gateway cat /etc/nginx/conf.d/gateway-routes/{DEPLOY_ID}-apk.conf")
sh(S + f"docker exec gateway cat /etc/nginx/conf.d/{DEPLOY_ID}.conf")
sh(S + f"ls -la /home/ubuntu/{DEPLOY_ID}/static/")
sh(S + f"ls -la /home/ubuntu/{DEPLOY_ID}/static/apk/ 2>/dev/null || echo NO_APK_DIR")

c.close()
