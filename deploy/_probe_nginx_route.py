import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

cmds = [
    "ls /home/ubuntu/gateway/conf.d/",
    "grep -rln '6b099\\|autodev' /home/ubuntu/gateway/conf.d/ /home/ubuntu/gateway/nginx.conf 2>/dev/null",
    "grep -A20 -B2 '6b099\\|autodev' /home/ubuntu/gateway/conf.d/*.conf 2>/dev/null | head -120",
    "ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/",
    "ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/ | head -10",
    # try a known APK URL via curl from server itself
    "curl -sk -o /dev/null -w 'HTTP=%{http_code}  size=%{size_download}\\n' https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/bini_health_coupon_20260504_114911_54f0.apk",
    "curl -sk -o /dev/null -w 'HTTP=%{http_code}\\n' https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/bini_health_coupon_20260504_114911_54f0.apk",
    "curl -sk -o /dev/null -w 'HTTP=%{http_code}\\n' https://newbb.test.bangbangvip.com/static/apk/bini_health_coupon_20260504_114911_54f0.apk",
    "curl -sk -o /dev/null -w 'HTTP=%{http_code}\\n' https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram_20260327_163902_ee97.zip",
]

for c in cmds:
    print("=" * 80)
    print("$", c)
    _, out, err = ssh.exec_command(c, timeout=30)
    o = out.read().decode(errors="replace")
    e = err.read().decode(errors="replace")
    if o: print(o)
    if e: print("ERR:", e)

ssh.close()
