"""Check current APK state on server and local."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=60)

def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=120)
    out = o.read().decode(errors='ignore')
    err = e.read().decode(errors='ignore')
    return out, err

print("=== downloads/ dir ===")
o, _ = run(f"ls -la /home/ubuntu/{DEPLOY_ID}/static/downloads/ 2>&1")
print(o)

print("=== static/apk dir ===")
o, _ = run(f"ls -la /home/ubuntu/{DEPLOY_ID}/static/apk/ 2>&1")
print(o)

print("=== git log on server ===")
o, _ = run(f"cd /home/ubuntu/{DEPLOY_ID} && git log --oneline -10 2>&1")
print(o)

print("=== HEAD commit ===")
o, _ = run(f"cd /home/ubuntu/{DEPLOY_ID} && git rev-parse HEAD 2>&1")
print(o)

print("=== flutter-builder image? ===")
o, _ = run("docker images | grep -i flutter 2>&1")
print(o)

print("=== last build log tail ===")
o, _ = run("tail -60 /tmp/flutter_build_home3bugs_v3.log 2>&1 | tail -60")
print(o)

c.close()
