from _ssh_helper import run
# nginx process tree
print("=== nginx processes with their PIDs and parents ===")
rc,out,err=run("ps -eo pid,ppid,user,cmd | grep -i nginx | grep -v grep", timeout=10)
print(out)
print("---")
# Find the nginx that owns 1790905 path
print("\n=== Find nginx config in mount namespace of pid 1101819 (system one) ===")
rc,out,err=run("sudo ls -la /proc/1101819/root/etc/nginx/ 2>&1 | head -20", timeout=10)
print(out)
print("\n=== conf.d listing in pid 1101819 ===")
rc,out,err=run("sudo ls /proc/1101819/root/etc/nginx/conf.d/ 2>&1", timeout=10)
print(out)
print("\n=== Read the nginx.conf used by pid 1101819 ===")
rc,out,err=run("sudo cat /proc/1101819/root/etc/nginx/nginx.conf 2>&1 | head -80", timeout=10)
print(out)
