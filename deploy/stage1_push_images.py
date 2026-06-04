import paramiko
import sys, time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ACR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_NS = "noob_ai_apps"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"

IMAGES = [
    ("backend", f"{DEPLOY_ID}-backend:latest"),
    ("admin-web", f"{DEPLOY_ID}-admin-web:latest"),
    ("h5-web", f"{DEPLOY_ID}-h5-web:latest"),
]

def run_ssh(host, port, username, password, command, timeout=120):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=username, password=password, timeout=15)
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    exit_code = stdout.channel.recv_exit_status()
    client.close()
    return out, err, exit_code

# Login to ACR
print("=== Logging into ACR ===")
out, err, code = run_ssh(HOST, PORT, USER, PASS,
    f"docker login --username={ACR_USER} --password={ACR_PASS} {ACR}", timeout=30)
print(f"Login: {out}")
if code != 0:
    print(f"Login failed: {err}")
    sys.exit(1)

for svc_name, local_tag in IMAGES:
    acr_tag = f"{ACR}/{ACR_NS}/{DEPLOY_ID}-{svc_name}:latest"
    print(f"\n=== Processing {svc_name} ===")
    
    # Tag
    print(f"Tagging {local_tag} -> {acr_tag}")
    out, err, code = run_ssh(HOST, PORT, USER, PASS,
        f"docker tag {local_tag} {acr_tag}", timeout=30)
    print(f"Tag: out={out} err={err} code={code}")
    
    # Push
    print(f"Pushing {acr_tag} ...")
    out, err, code = run_ssh(HOST, PORT, USER, PASS,
        f"docker push {acr_tag}", timeout=300)
    print(f"Push: out={out}")
    if err:
        print(f"Push stderr: {err[:500]}")
    if code != 0:
        print(f"Push FAILED for {svc_name}!")
        sys.exit(1)
    print(f"Push SUCCESS for {svc_name}!")

print("\n=== All images pushed successfully! ===")
