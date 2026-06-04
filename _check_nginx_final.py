from _ssh_helper import run

print("=== Gateway nginx containers ===")
rc, out, err = run("sudo docker ps --format '{{.Names}}' | grep -i gateway", timeout=20)
print(out)

print("\n=== Gateway nginx config for this UUID ===")
rc, out, err = run(
    "sudo docker exec gateway-nginx sh -c 'find /etc/nginx -type f | xargs grep -l 6b099ed3 2>/dev/null'",
    timeout=20,
)
print(out, "ERR:", err)

print("\n=== Show the conf content ===")
rc, out, err = run(
    "sudo docker exec gateway-nginx sh -c 'cat /etc/nginx/conf.d/projects/6b099ed3*.conf 2>/dev/null || cat /etc/nginx/sites-enabled/6b099ed3*.conf 2>/dev/null || find /etc/nginx -name \"*6b099ed3*\" -exec cat {} \\;'",
    timeout=20,
)
print(out)
print("ERR:", err[:500] if err else "")
