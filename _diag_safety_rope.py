"""Run diagnose commands on remote server via SSH."""
import sys
sys.path.insert(0, ".")
from _ssh_helper import run

CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"
H5_CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-h5"

# script for openapi inspection (run inside backend container)
PY_OPENAPI = (
    "import sys,json,urllib.request as u; "
    "d=json.loads(u.urlopen('http://127.0.0.1:8000/openapi.json').read()); "
    "ps=[p for p in d.get('paths',{}) if 'safety-rope' in p]; "
    "print('total_paths='+str(len(d.get('paths',{})))); "
    "print('safety_rope_paths='+str(len(ps))); "
    "print('\\n'.join(ps))"
)

steps = [
    ("inside-container probe localhost API",
     f"docker exec {CONTAINER} sh -c \"curl -sk -o /dev/null -w 'inside_status=%{{http_code}}\\n' http://127.0.0.1:8000/api/safety-rope/status\""),
    ("openapi paths matching safety-rope",
     f"docker exec {CONTAINER} python3 -c \"{PY_OPENAPI}\""),
    ("backend logs grep safety_rope/ImportError",
     f"docker logs {CONTAINER} 2>&1 | grep -iE 'safety_rope|include_router|ImportError|Traceback' | tail -50"),
    ("backend file presence",
     f"docker exec {CONTAINER} ls -la /app/app/api/safety_rope_v1.py"),
    ("backend main.py snippet for safety_rope",
     f"docker exec {CONTAINER} grep -n 'safety_rope' /app/app/main.py | head -20"),
    ("h5 source page presence",
     f"docker exec {H5_CONTAINER} sh -c 'ls -la /app/src/app/care-home/page.tsx 2>&1 || echo NO_SRC; ls -la /app/.next 2>&1 | head'"),
    ("h5 built outputs for care-home (find)",
     f"docker exec {H5_CONTAINER} sh -c 'find /app/.next -path \"*care-home*\" 2>/dev/null | head -10'"),
    ("h5 grep safety-rope-entry in .next",
     f"docker exec {H5_CONTAINER} sh -c 'grep -rl \"safety-rope-entry\" /app/.next 2>/dev/null | head -5 || echo NOT_FOUND'"),
]

for title, cmd in steps:
    print("====", title, "====")
    rc, out = run(cmd, timeout=120)
    print(out.strip())
    print()
