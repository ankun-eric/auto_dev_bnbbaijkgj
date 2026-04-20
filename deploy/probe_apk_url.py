"""Probe why APK URL 404s - check nginx routing, file serving path."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=60)

def run(cmd, timeout=60):
    print(f"\n>>> {cmd[:240]}")
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode(errors='ignore')
    err = e.read().decode(errors='ignore')
    if out.strip(): print(out[-3500:])
    if err.strip(): print('STDERR:', err[-1500:])
    return out

# Try a known-good miniprogram zip URL (they should work):
run('curl -sS -o /dev/null -w "mp HTTP %{http_code}\\n" -I "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/static/downloads/miniprogram_latest.zip"')

# Try static/apk/ path
run('curl -sS -o /dev/null -w "apk1 HTTP %{http_code}\\n" -I "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/bini_health.apk"')

# Maybe root path differs, try /apk/bini_health.apk
run('curl -sS -o /dev/null -w "apk2 HTTP %{http_code}\\n" -I "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/bini_health.apk"')

# What is the docker/container/nginx routing? Check running containers
run("docker ps --format '{{.Names}} {{.Image}} {{.Ports}}' | head -40")

# Find gateway-nginx / nginx conf files
run("docker ps --format '{{.Names}}' | grep -iE 'gateway|nginx' | head -5")

# Check if there is a container named with deploy id
run(f"docker ps --format '{{{{.Names}}}} {{{{.Ports}}}}' | grep -E '{DEPLOY_ID[:8]}|home3bugs|bini' | head -20")

# Inspect gateway nginx config
run("ls /home/ubuntu/gateway-nginx/conf.d/ 2>/dev/null | head -20")
run(f"grep -l '{DEPLOY_ID}' /home/ubuntu/gateway-nginx/conf.d/*.conf 2>/dev/null | head -5")

c.close()
