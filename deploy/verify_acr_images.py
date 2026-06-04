import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ACR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_NS = "noob_ai_apps"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

images = ["backend", "admin-web", "h5-web"]

for svc in images:
    tag = f"{ACR}/{ACR_NS}/{DEPLOY_ID}-{svc}:latest"
    print(f"\n=== Verifying {tag} ===")
    stdin, stdout, stderr = client.exec_command(
        f"docker manifest inspect {tag} 2>&1 | head -5", timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    exit_code = stdout.channel.recv_exit_status()
    if exit_code == 0:
        print(f"  VERIFIED OK")
        print(out[:300] if out else "(no output)")
    else:
        print(f"  VERIFY FAILED: {err[:500]}")

client.close()
print("\n=== ACR image verification complete ===")
