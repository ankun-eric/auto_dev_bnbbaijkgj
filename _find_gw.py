from _ssh_helper import run
# Find any container exposing 443 or having nginx
rc,out,err=run("sudo docker ps -a --format '{{.Names}}|{{.Image}}|{{.Ports}}|{{.Status}}' | grep -iE 'nginx|gateway|proxy|443' | head -30", timeout=20)
print("Containers with nginx/gateway/443:")
print(out)
print("---")
# Check rootless docker socket
rc,out,err=run("ps aux | grep -i 'rootless\\|nginx' | grep -v grep | head -20", timeout=20)
print(out)
