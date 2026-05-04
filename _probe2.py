#!/usr/bin/env python3
import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PASS="Newbang888"
client=paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=60)
DEPLOY="6b099ed3-7175-4a78-91f4-44570c84ed27"
cmd = f"""
echo '== test existing apk =='
curl -sI 'https://newbb.test.bangbangvip.com/autodev/{DEPLOY}/apk/bini_health_book_after_pay_20260503_203439_8a32.apk' | head -5
echo '== gateway nginx.conf =='
cat /home/ubuntu/gateway/nginx.conf 2>/dev/null | head -80
echo '== conf.d listing =='
ls -la /home/ubuntu/gateway/conf.d/ 2>/dev/null
echo '== docker exec gateway ls /etc/nginx/conf.d =='
echo '{PASS}' | sudo -S docker exec gateway ls /etc/nginx/conf.d/ 2>&1 | head -20
echo '== gateway grep DEPLOY in conf.d =='
echo '{PASS}' | sudo -S grep -RIn '{DEPLOY}\\|/apk/' /home/ubuntu/gateway/ 2>/dev/null | head -40
echo '== gateway docker inspect mounts =='
echo '{PASS}' | sudo -S docker inspect gateway --format '{{{{json .Mounts}}}}' 2>&1
"""
stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
print(stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err.strip(): print("STDERR:", err)
client.close()
