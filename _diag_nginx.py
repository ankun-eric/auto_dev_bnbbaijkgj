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

run(f"docker exec gateway sh -c 'grep -rl \"{DEPLOY_ID}\" /etc/nginx/ 2>/dev/null'", "find nginx confs")
run(f"docker exec gateway sh -c 'cat /etc/nginx/conf.d/*.conf 2>/dev/null | grep -A 20 \"{DEPLOY_ID}\" | head -120'", "show conf")
run(f"docker network inspect $(docker inspect gateway --format '{{{{range $k,$v := .NetworkSettings.Networks}}}}{{{{$k}}}} {{{{end}}}}' | tr ' ' '\\n' | head -1) --format '{{{{json .Containers}}}}' | python3 -c 'import sys,json; d=json.load(sys.stdin); [print(v[\"Name\"], v[\"IPv4Address\"]) for v in d.values()]' 2>&1 | head -20", "gateway network containers")
run(f"docker exec gateway curl -s -o /dev/null -w 'http=%{{http_code}}\\n' http://{DEPLOY_ID}-h5:3000/apk/{APK}", "from gateway -> h5 :3000 /apk/")
run(f"docker exec gateway curl -s -o /dev/null -w 'http=%{{http_code}}\\n' http://{DEPLOY_ID}-h5:3000/autodev/{DEPLOY_ID}/apk/{APK}", "from gateway -> h5 :3000 /autodev/.../apk/")
run(f"docker exec {DEPLOY_ID}-h5 wget -q -O - http://localhost:3000/apk/{APK} -S 2>&1 | head -5", "inside h5 wget")
c.close()
