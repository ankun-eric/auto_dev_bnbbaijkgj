from _ssh_helper import run
# As ubuntu (without sudo), rootless docker is the user's own
rc,out,err=run("docker ps --format '{{.Names}}|{{.Image}}|{{.Ports}}' 2>&1", timeout=20)
print("ubuntu's containers:")
print(out)
print("---")
rc,out,err=run("docker ps --filter publish=443 --format '{{.Names}}|{{.Ports}}' 2>&1", timeout=20)
print("443 publish:", out)
print("---")
rc,out,err=run("docker ps --filter publish=80 --format '{{.Names}}|{{.Ports}}' 2>&1", timeout=20)
print("80 publish:", out)
