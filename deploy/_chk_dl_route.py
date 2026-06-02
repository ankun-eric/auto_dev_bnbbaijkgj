import sys
sys.path.insert(0, ".")
from deploy._sshlib import run

code, out, err = run("docker exec gateway-nginx sh -lc 'nginx -T 2>/dev/null'", timeout=60)
lines = out.splitlines()
for i, ln in enumerate(lines):
    low = ln.lower()
    if ("apk" in low or "/data/static" in low or "6b099ed3" in low or ".zip" in low or "alias" in low and "static" in low):
        print(i, ln.rstrip())
print("--- searching 6b099ed3 blocks (location + alias/root) ---")
for i, ln in enumerate(lines):
    if "6b099ed3" in ln and ("location" in ln.lower()):
        print("\n".join(lines[i:i+12]))
        print("====")
