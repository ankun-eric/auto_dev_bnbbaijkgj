from _ssh_helper import run
print("=== docker-compose.prod.yml ===")
rc,out,err=run("cat /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/docker-compose.prod.yml 2>&1", timeout=10)
print(out)
print("\n=== Find existing ports usage ===")
rc,out,err=run("sudo ss -tlnp | grep -E ':18[0-9]{3}|:19[0-9]{3}' | head -20", timeout=10)
print(out)
