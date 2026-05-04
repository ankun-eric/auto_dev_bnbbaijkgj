#!/usr/bin/env python3
import paramiko, sys
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASS="Newbang888"
client=paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=60)
DEPLOY="6b099ed3-7175-4a78-91f4-44570c84ed27"
cmd = f"""
echo '== gateway containers =='
echo '{PASS}' | sudo -S docker ps --format 'table {{{{.Names}}}}\\t{{{{.Image}}}}\\t{{{{.Ports}}}}' 2>/dev/null | grep -iE 'gateway|nginx' || true
echo '== /data/static/apk listing =='
ls -la /data/static/apk/ 2>/dev/null | head -30
echo '== project home dir =='
ls -la /home/ubuntu/{DEPLOY}/ 2>/dev/null | head -30
echo '== gateway nginx config search =='
echo '{PASS}' | sudo -S find /home/ubuntu -maxdepth 4 -name '*.conf' 2>/dev/null | head -20
echo '== gateway nginx grep DEPLOY =='
echo '{PASS}' | sudo -S grep -RIn '{DEPLOY}' /home/ubuntu 2>/dev/null | head -30
echo '== docker exec gateway-nginx ls /usr/share/nginx/html =='
echo '{PASS}' | sudo -S docker exec gateway-nginx ls /usr/share/nginx/html 2>/dev/null | head -20
echo '== gateway-nginx find apk dir =='
echo '{PASS}' | sudo -S docker exec gateway-nginx find /usr/share/nginx/html -maxdepth 3 -type d -name 'apk' 2>/dev/null
echo '== nginx config inside gateway =='
echo '{PASS}' | sudo -S docker exec gateway-nginx cat /etc/nginx/conf.d/default.conf 2>/dev/null | head -100
"""
stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err.strip(): print("STDERR:", err)
client.close()
