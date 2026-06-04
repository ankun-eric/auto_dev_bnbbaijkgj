from _ssh_helper import run
rc,out,err=run("sudo docker ps --format '{{.Names}}|{{.Ports}}'", timeout=20)
print(out)
print("---")
rc,out,err=run("sudo netstat -tlnp 2>/dev/null | head -40 || sudo ss -tlnp | head -40", timeout=20)
print(out)
