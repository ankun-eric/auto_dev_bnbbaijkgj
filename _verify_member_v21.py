"""Verify backend schema has new member_id columns + run basic API smoke."""
import paramiko, urllib.request, ssl, json
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username="ubuntu", password="Newbang888", timeout=60)

def run(cmd, timeout=120):
    si, so, se = c.exec_command(cmd, timeout=timeout)
    out = so.read().decode("utf-8", "replace")
    err = se.read().decode("utf-8", "replace")
    code = so.channel.recv_exit_status()
    return code, out, err

print("=== schema check via mysql ===")
sql = "DESCRIBE home_safety_device_binding;"
code, out, err = run(
    f"docker exec {DEPLOY_ID}-db mysql -uroot -proot ai_doctor -e \"{sql}\" 2>&1"
)
print(out[-2000:])

sql2 = "DESCRIBE home_safety_alarm;"
code, out, err = run(
    f"docker exec {DEPLOY_ID}-db mysql -uroot -proot ai_doctor -e \"{sql2}\" 2>&1"
)
print(out[-2000:])

sql3 = "DESCRIBE home_safety_emergency_contact;"
code, out, err = run(
    f"docker exec {DEPLOY_ID}-db mysql -uroot -proot ai_doctor -e \"{sql3}\" 2>&1"
)
print(out[-2000:])

c.close()

print("\n=== API smoke ===")
ctx = ssl.create_default_context()
for path in ["/api/health", "/health"]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=15, context=ctx) as r:
            print(f"  {r.status} {path}")
            break
    except Exception as e:
        print(f"  ERR {path}: {e}")

# Check the H5 home-safety page
try:
    with urllib.request.urlopen(BASE + "/home-safety", timeout=15, context=ctx) as r:
        body = r.read().decode("utf-8", "replace")
        print(f"  {r.status} /home-safety  len={len(body)}")
except Exception as e:
    print(f"  ERR /home-safety: {e}")
