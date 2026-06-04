"""Probe backend routes directly."""
import sys
sys.path.insert(0, ".")
from _ssh_helper import run

rc, out, _ = run("docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' 6b099ed3-7175-4a78-91f4-44570c84ed27-backend", timeout=15)
ip = out.strip().split()[0]
print("backend IP:", ip)

paths = ["/", "/api", "/api/", "/openapi.json", "/docs", "/api/admin/login", "/api/auth/login", "/api/v1/login", "/login"]
for p in paths:
    print(f"\n--- GET {p} ---")
    rc, out, _ = run(f"curl -s -o /tmp/_b.out -w 'HTTP %{{http_code}}\\n' http://{ip}:8000{p}", timeout=15)
    print(out.strip())
    rc2, body, _ = run("head -c 300 /tmp/_b.out", timeout=10)
    print("body:", body.replace("\n", " ").strip()[:300])
