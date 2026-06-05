"""Fix admin container: rebuild with correct basePath, restart."""
import paramiko, sys, time

HOST, USER, PASS = "newbb.test.bangbangvip.com", "ubuntu", "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PDIR = f"/home/ubuntu/{DID}"
ACR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"

def run(ssh, cmd, timeout=30):
    print(f"\n>>> {cmd[:120]}", flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out[-800:], flush=True)
    if err.strip() and ec != 0: print("ERR:", err[-300:], flush=True)
    return ec, out, err

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PASS, timeout=15)
print("Connected", flush=True)

# Git pull latest
run(ssh, f"cd {PDIR} && git pull origin master 2>&1", timeout=30)

# Login ACR
run(ssh, f"docker login --username ankun888 --password xiaobai888 {ACR}")

# Rebuild admin with build args
print("\n=== Rebuilding admin with basePath=/admin ===", flush=True)
run(ssh, f"cd {PDIR}/admin-web && docker build --build-arg NEXT_PUBLIC_API_URL=/api --build-arg NEXT_PUBLIC_BASE_PATH=/admin -f ../deploy/Dockerfile.admin -t {ACR}/noob_ai_apps/{DID}-admin-web:latest . 2>&1", timeout=600)

# Stop, rm, recreate admin
run(ssh, f"docker stop {DID}-admin 2>/dev/null; docker rm {DID}-admin 2>/dev/null; echo cleaned", timeout=15)

# Recreate using docker compose
run(ssh, f"cd {PDIR}/deploy && docker compose -f docker-compose.prod.yml up -d admin-web 2>&1", timeout=60)

# Wait for healthy
print("\n=== Waiting for admin healthy ===", flush=True)
for i in range(20):
    time.sleep(10)
    stdin, stdout, stderr = ssh.exec_command(
        f"docker ps --filter name={DID}-admin --format '{{{{.Names}}}} {{{{.Status}}}}'", timeout=10)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    if 'healthy' in out.lower():
        print(f"[{i}] Admin healthy: {out}", flush=True)
        break
    print(f"[{i}] {out}", flush=True)
else:
    print("TIMEOUT", flush=True)

# Final check
run(ssh, f"docker ps --filter name={DID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'")
ssh.close()
print("\nDone", flush=True)
