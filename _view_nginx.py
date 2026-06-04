from _ssh_helper import run
rc,out,err=run("sudo cat /etc/nginx/conf.d/routes/6b099ed3-7175-4a78-91f4-44570c84ed27.conf", timeout=20)
print(out)
print("---")
# Check parent conf
rc,out,err=run("sudo cat /etc/nginx/conf.d/default.conf 2>/dev/null | head -80", timeout=20)
print(out)
