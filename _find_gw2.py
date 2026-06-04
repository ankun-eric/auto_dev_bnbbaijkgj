from _ssh_helper import run
# rootless docker proxies port 80/443 to a container. Find which.
rc,out,err=run("sudo docker ps -a --filter publish=443 --format '{{.Names}}|{{.Image}}|{{.Ports}}'", timeout=20)
print("443 publish:", out)
print("---")
rc,out,err=run("sudo docker ps -a --filter publish=80 --format '{{.Names}}|{{.Image}}|{{.Ports}}'", timeout=20)
print("80 publish:", out)
print("---")
# Check who owns rootlessport pid
rc,out,err=run("sudo ps -ef | grep -i rootless | grep -v grep | head -5", timeout=20)
print(out)
print("---")
# user docker
rc,out,err=run("sudo -u $(ps -o user= -p 1790905 2>/dev/null) docker ps 2>&1 | head -10 || true", timeout=20)
print(out)
