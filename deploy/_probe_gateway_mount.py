import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ssh_helper import create_client, run_cmd

s = create_client()
print("=== nginx main conf ===")
print(run_cmd(s, "cat /home/ubuntu/gateway/nginx.conf")[0])
print("=== /home/ubuntu/gateway/conf.d listing ===")
print(run_cmd(s, "ls -la /home/ubuntu/gateway/conf.d/ 2>&1")[0])
print(run_cmd(s, "ls -la /home/ubuntu/gateway/conf.d/routes/ 2>&1 | head -30")[0])
print("=== grep apk in gateway conf ===")
print(run_cmd(s, "grep -rn 'apk' /home/ubuntu/gateway/conf.d/ 2>&1 | head -40")[0])
print("=== grep 6b099ed3 in gateway conf ===")
print(run_cmd(s, "grep -rn '6b099ed3-7175' /home/ubuntu/gateway/conf.d/ 2>&1 | head -40")[0])
