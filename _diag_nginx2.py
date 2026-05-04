#!/usr/bin/env python3
import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASS="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
APK="bini_health_coupon_mall_20260504_130854_91a5.apk"

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PASS,timeout=60)

def run(cmd, lbl=""):
    if lbl: print(f"\n>>> {lbl}")
    _,o,e=c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8","replace"))
    er=e.read().decode("utf-8","replace")
    if er.strip(): print("ERR:",er[:300])

# nginx container mounts
run("docker inspect gateway --format '{{json .Mounts}}' | python3 -m json.tool", "gateway mounts")
# does gateway container see /data/static/apk?
run(f"docker exec gateway ls -la /data/static/apk/ 2>&1 | head -10", "ls /data/static/apk in gateway")
run(f"docker exec gateway cat /etc/nginx/conf.d/gateway-routes/{DEPLOY_ID}-apk.conf 2>&1", "gateway-routes apk conf")
run(f"docker exec gateway cat /etc/nginx/nginx.conf 2>&1 | head -60", "main nginx.conf")
# check default location for /apk via nginx
run(f"docker exec gateway nginx -T 2>/dev/null | grep -B2 -A8 '/apk/'", "nginx -T grep apk")

c.close()
