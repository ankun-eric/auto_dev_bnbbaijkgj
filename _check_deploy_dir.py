# -*- coding: utf-8 -*-
import paramiko, sys
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888", timeout=30)
for cmd in [
    "docker inspect gateway --format '{{json .Mounts}}' | python3 -m json.tool 2>/dev/null",
    "docker exec gateway sh -c 'cat /etc/nginx/conf.d/*.conf 2>/dev/null | grep -B1 -A6 \"6b099ed3\"' 2>&1 | head -60",
    "docker exec gateway sh -c 'ls /static-files/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/ 2>&1' | head -5",
]:
    print(f"### {cmd}")
    i,o,e = c.exec_command(cmd)
    sys.stdout.write(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip(): sys.stdout.write("ERR:"+err)
c.close()
