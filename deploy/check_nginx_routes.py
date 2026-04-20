"""Check what nginx routes exist for this project."""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=60)

def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=60)
    return o.read().decode(errors='ignore') + e.read().decode(errors='ignore')

print("=== route files ===")
print(run("ls /home/ubuntu/gateway-nginx/conf.d/routes/ 2>&1 | head -50"))

print("\n=== grep deploy id in route files ===")
print(run("grep -lr '6b099ed3-7175-4a78-91f4-44570c84ed27' /home/ubuntu/gateway-nginx/conf.d/ 2>&1 | head -10"))

print("\n=== find route config for this id ===")
print(run("ls /home/ubuntu/gateway-nginx/conf.d/routes/ 2>&1 | grep -i '6b099ed3\\|home3bugs\\|bini' | head -10"))

print("\n=== read route file if found ===")
print(run("cat /home/ubuntu/gateway-nginx/conf.d/routes/6b099ed3*.conf 2>&1 | head -100"))

print("\n=== find all routes matching autodev pattern ===")
print(run("grep -rn 'autodev/6b099ed3' /home/ubuntu/gateway-nginx/ 2>&1 | head -30"))

print("\n=== currently served static paths for this project (via docker exec gateway) ===")
print(run("docker exec gateway cat /etc/nginx/conf.d/routes/6b099ed3*.conf 2>&1 | head -100"))

# probe which path patterns work
for url in [
    "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health.apk",
    "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/bini_health.apk",
    "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health_android-home3bugs-20260421-034208.apk",
    "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_latest.zip",
    "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram_latest.zip",
    "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/static/downloads/miniprogram_latest.zip",
]:
    print(f"\n{url}")
    print(run(f'curl -sS -o /dev/null -w "HTTP %{{http_code}} size=%{{size_download}}" -I "{url}"'))

c.close()
