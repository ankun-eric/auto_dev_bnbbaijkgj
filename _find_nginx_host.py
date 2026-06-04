from _ssh_helper import run
# Find nginx config dir
rc,out,err=run("sudo ls /etc/nginx/sites-enabled/ 2>&1 || sudo ls /etc/nginx/conf.d/ 2>&1", timeout=20)
print("Nginx conf dirs:")
print(out)
print("---")
rc,out,err=run("sudo grep -rl '6b099ed3\\|autodev' /etc/nginx/ 2>/dev/null | head -10", timeout=20)
print("Files mentioning autodev or our UUID:")
print(out)
print("---")
rc,out,err=run("sudo grep -rl 'newbb.test' /etc/nginx/ 2>/dev/null | head -10", timeout=20)
print("Files mentioning newbb:")
print(out)
