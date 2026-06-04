import paramiko, time

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"
DP_ID = "630774"
DP_KEY = "a9120bdeaa29f3c28d1448508624afb6"
DOMAIN = "chat.benne-ai.com"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=120):
    print(f"  CMD: {cmd[:140]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if out and len(out) < 500:
        print(f"  OUT: {out}")
    if err and len(err) > 5:
        print(f"  ERR: {err[:300]}")
    return out, err, code

# Step 1: Install acme.sh
print("=== Step 1: 安装 acme.sh ===")
out, err, code = run(
    "curl -fsSL https://get.acme.sh | sh -s email=admin@benne-ai.com 2>&1",
    timeout=60
)
if code != 0:
    # Retry with gitee mirror
    print("  GitHub failed, try Gitee mirror...")
    out, err, code = run(
        "curl -fsSL https://gitee.com/neilpang/acme.sh/raw/master/acme.sh | sh -s email=admin@benne-ai.com 2>&1",
        timeout=60
    )
print(f"  Install result code: {code}")

# Step 2: Verify acme.sh
print("\n=== Step 2: 验证 acme.sh ===")
run("source ~/.bashrc && ~/.acme.sh/acme.sh --version 2>&1 || true", timeout=10)

# Step 3: Set DNSPod API credentials
print("\n=== Step 3: 配置 DNSPod API ===")
run(f"export DP_Id={DP_ID} && export DP_Key={DP_KEY}", timeout=5)
run(
    f"bash -c 'export DP_Id={DP_ID} DP_Key={DP_KEY}; "
    f"~/.acme.sh/acme.sh --set-default-ca --server letsencrypt 2>&1'",
    timeout=30
)

# Step 4: Issue certificate via DNS
print(f"\n=== Step 4: 签发 Let's Encrypt 证书 ({DOMAIN}) ===")
out, err, code = run(
    f"bash -c 'export DP_Id={DP_ID} DP_Key={DP_KEY}; "
    f"~/.acme.sh/acme.sh --issue --dns dns_dp -d {DOMAIN} -d '*.{DOMAIN}' "
    f"--keylength ec-256 --force 2>&1'",
    timeout=180
)
print(f"  Issue: code={code}")
if code != 0:
    print(f"  签发失败，查看错误: {err[:500]}")

# Step 5: Install cert to gateway ssl dir
print(f"\n=== Step 5: 安装证书到 gateway ssl 目录 ===")
SSL_DIR = "/home/ubuntu/gateway/ssl"
run(f"sudo mkdir -p {SSL_DIR}", timeout=5)

# acme.sh install-cert
out, err, code = run(
    f"bash -c 'export DP_Id={DP_ID} DP_Key={DP_KEY}; "
    f"~/.acme.sh/acme.sh --install-cert -d {DOMAIN} "
    f"--key-file {SSL_DIR}/{DOMAIN}.key "
    f"--fullchain-file {SSL_DIR}/{DOMAIN}.crt "
    f"--reloadcmd \"sudo docker exec gateway-nginx nginx -s reload\" 2>&1'",
    timeout=60
)
print(f"  Install cert: code={code} {out[:300] if out else ''}")

# Step 6: Fix permissions
print("\n=== Step 6: 修正权限 ===")
run(f"sudo chmod 644 {SSL_DIR}/{DOMAIN}.crt 2>/dev/null || true", timeout=5)
run(f"sudo chmod 600 {SSL_DIR}/{DOMAIN}.key 2>/dev/null || true", timeout=5)

# Step 7: Verify new cert
print("\n=== Step 7: 验证新证书 ===")
out, err, code = run(
    f"sudo openssl x509 -in {SSL_DIR}/{DOMAIN}.crt -noout -subject -dates -issuer 2>&1",
    timeout=15
)
print(f"  {out}")

# Step 8: Reload nginx
print("\n=== Step 8: 重载 Nginx ===")
run("sudo docker exec gateway-nginx nginx -t 2>&1", timeout=15)
run("sudo docker exec gateway-nginx nginx -s reload 2>&1", timeout=10)

# Step 9: Test
print("\n=== Step 9: 验证HTTPS ===")
time.sleep(3)
out, err, code = run("curl -svI https://chat.benne-ai.com/ 2>&1 | grep -iE 'SSL|subject|issuer|expire|CN|verify'", timeout=20)
print(f"  {out}")

# Step 10: Show auto-renew info
print("\n=== Step 10: 自动续期状态 ===")
run("bash -c '~/.acme.sh/acme.sh --list 2>&1'", timeout=10)
run("crontab -l 2>/dev/null | grep acme", timeout=5)

client.close()
print("\n=== acme.sh + Let's Encrypt 配置完成 ===")
