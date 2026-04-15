import paramiko
import urllib.request
import urllib.error
import ssl

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

# 1. Check container status via SSH
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

print("=== Container Status ===")
stdin, stdout, stderr = ssh.exec_command(
    f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'",
    timeout=30
)
print(stdout.read().decode("utf-8", errors="replace").strip())

print("\n=== Network Connectivity ===")
stdin, stdout, stderr = ssh.exec_command(
    f"docker network inspect {DEPLOY_ID}-network --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'",
    timeout=30
)
print("Containers in network:", stdout.read().decode("utf-8", errors="replace").strip())

ssh.close()

# 2. Check HTTP endpoints
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    (f"{BASE}/api/health", "Backend API Health"),
    (f"{BASE}/", "H5 Web"),
    (f"{BASE}/admin/", "Admin Web"),
]

print("\n=== HTTP Endpoint Check ===")
for url, name in urls:
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "DeployCheck/1.0")
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        code = resp.getcode()
        body = resp.read(500).decode("utf-8", errors="replace")
        print(f"[OK]  {name}: HTTP {code} - {url}")
    except urllib.error.HTTPError as e:
        print(f"[WARN] {name}: HTTP {e.code} - {url}")
    except Exception as e:
        print(f"[FAIL] {name}: {e} - {url}")

print("\n=== Deployment Summary ===")
print(f"H5 Web:    {BASE}/")
print(f"Admin:     {BASE}/admin/")
print(f"API:       {BASE}/api/")
