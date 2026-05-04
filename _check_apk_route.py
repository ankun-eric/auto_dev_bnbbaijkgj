#!/usr/bin/env python3
"""Inspect docker containers + apk path served by h5-web."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=60)

cmds = [
    f"echo '=== docker ps for deploy ==='; docker ps --format '{{{{.Names}}}}\t{{{{.Image}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID[:8]} || true",
    f"echo '=== ls h5-web/public/apk ==='; ls -la /home/ubuntu/{DEPLOY_ID}/h5-web/public/apk/ 2>&1",
    f"echo '=== nginx confs containing autodev/{DEPLOY_ID} ==='; sudo -S grep -rn '{DEPLOY_ID}' /etc/nginx/conf.d/ 2>&1 | head -40 <<< '{PASS}'",
    f"echo '=== gateway-nginx container ==='; docker ps --format '{{{{.Names}}}}\t{{{{.Image}}}}' | grep -i nginx || true",
    f"echo '=== try direct curl on local ==='; curl -s -o /dev/null -w '%{{http_code}}\\n' 'http://127.0.0.1/autodev/{DEPLOY_ID}/apk/bini_health_coupon_mall_20260504_130854_91a5.apk' 2>&1",
    f"echo '=== https curl follow ==='; curl -sL -o /dev/null -w 'http=%{{http_code}} size=%{{size_download}} url=%{{url_effective}}\\n' 'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/apk/bini_health_coupon_mall_20260504_130854_91a5.apk'",
]
for c in cmds:
    print(f"\n>>> {c[:120]}")
    stdin, stdout, stderr = client.exec_command(c, timeout=60)
    print(stdout.read().decode("utf-8", "replace"))
    e = stderr.read().decode("utf-8", "replace")
    if e.strip():
        print("STDERR:", e[:300])

client.close()
