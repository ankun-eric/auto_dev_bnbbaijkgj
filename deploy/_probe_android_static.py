import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ssh_helper import create_client, run_cmd

s = create_client()
print("=== /var/www/autodev/<id>/apk/ ===")
print(run_cmd(s, "ls -la /var/www/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/ 2>&1")[0])
print("=== sudo -n available ===")
o, e, c = run_cmd(s, "sudo -n true 2>&1; echo rc=$?")
print(o, e, c)
print("=== chown owner of that dir ===")
print(run_cmd(s, "stat -c '%U:%G %a' /var/www/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/ 2>&1")[0])
print("=== full nginx location for /apk/ ===")
print(run_cmd(s, "sed -n '50,70p' /etc/nginx/conf.d/routes/6b099ed3-7175-4a78-91f4-44570c84ed27.conf")[0])
