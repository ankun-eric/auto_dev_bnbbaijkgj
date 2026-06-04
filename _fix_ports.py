"""Manually edit docker-compose.prod.yml to add ports cleanly."""
from _ssh_helper import run, put_file

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"

# Restore from backup first
print("=== Restore from backup ===")
rc, out, err = run(f"cd {PROJ_DIR} && cp docker-compose.prod.yml.bak.v2 docker-compose.prod.yml 2>&1", timeout=10)
print(out, err)

# Download the file, edit locally, upload
import tempfile
print("\n=== Download original ===")
import paramiko
from _ssh_helper import get_client
c = get_client()
sftp = c.open_sftp()
sftp.get(f"{PROJ_DIR}/docker-compose.prod.yml", "_compose_orig.yml")
sftp.close()
c.close()

with open("_compose_orig.yml", "r", encoding="utf-8") as f:
    content = f.read()

# Add ports section after each expose
import re

# backend (8000): add ports 19400:8000
content = content.replace(
    '''    expose:
      - "8000"
    depends_on:
      db:''',
    '''    expose:
      - "8000"
    ports:
      - "19400:8000"
    depends_on:
      db:''',
    1,
)

# admin-web (3000): expose+depends_on backend (not db)
content = content.replace(
    '''    expose:
      - "3000"
    depends_on:
      - backend
    networks:
      app-network:
        aliases:
          - 6b099ed3-7175-4a78-91f4-44570c84ed27-admin''',
    '''    expose:
      - "3000"
    ports:
      - "19401:3000"
    depends_on:
      - backend
    networks:
      app-network:
        aliases:
          - 6b099ed3-7175-4a78-91f4-44570c84ed27-admin''',
    1,
)

# h5-web (3001)
content = content.replace(
    '''    expose:
      - "3001"
    depends_on:
      - backend
    networks:
      app-network:
        aliases:
          - 6b099ed3-7175-4a78-91f4-44570c84ed27-h5''',
    '''    expose:
      - "3001"
    ports:
      - "19402:3001"
    depends_on:
      - backend
    networks:
      app-network:
        aliases:
          - 6b099ed3-7175-4a78-91f4-44570c84ed27-h5''',
    1,
)

with open("_compose_new.yml", "w", encoding="utf-8") as f:
    f.write(content)

print("Local edit done. Show diff lines with 'ports:':")
for i, line in enumerate(content.splitlines()):
    if "ports:" in line or "19400" in line or "19401" in line or "19402" in line:
        print(f"  L{i}: {line}")

# Upload
put_file("_compose_new.yml", f"{PROJ_DIR}/docker-compose.prod.yml")
print("\nUploaded")

print("\n=== Verify on remote ===")
rc, out, err = run(f"grep -nE 'ports:|1940' {PROJ_DIR}/docker-compose.prod.yml", timeout=10)
print(out)

print("\n=== Recreate ===")
rc, out, err = run(
    f"cd {PROJ_DIR} && sudo docker compose -f docker-compose.prod.yml up -d 2>&1 | tail -30",
    timeout=300,
)
print(out)

print("\n=== Verify ports listening ===")
rc, out, err = run("sudo ss -tlnp | grep -E ':1940[0-2]'", timeout=10)
print(out)

print("\n=== Smoke test ===")
import time
time.sleep(8)
rc, out, err = run(
    f"curl -sk -w '\\nHTTP %{{http_code}}\\n' "
    f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/home_safety/callback/alarm "
    f"-X POST -H 'Content-Type: application/json' "
    f"--data '{{\"msgId\":\"setup_ok_v2_a\",\"param\":{{\"devId\":\"NOEXIST1\",\"devType\":\"1\",\"occurTime\":1547100617645,\"gwId\":\"GW1\"}},\"dataType\":\"call-msg\"}}'",
    timeout=30,
)
print("Callback:", out)

rc, out, err = run(
    f"curl -sk -o /dev/null -w 'HTTP %{{http_code}}\\n' "
    f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/admin/home-safety",
    timeout=30,
)
print("Admin:", out)
