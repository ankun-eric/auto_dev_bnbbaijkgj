import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
for path in ["/api/health", "/api/ai-home-config", "/", "/admin/", "/admin/home-settings/ai-home-config/", "/admin/home-settings/ai-home-config/logs/"]:
    cmd = f"curl -sL -o /dev/null -w 'HTTP_CODE=%{{http_code}}' {BASE}{path}"
    _, out, _ = ssh.exec_command(cmd, timeout=30)
    print(f"{path:55} -> {out.read().decode().strip()}")

# Show actual ai-home-config response
_, out, _ = ssh.exec_command(f"curl -sL {BASE}/api/ai-home-config | head -c 800", timeout=30)
print("\n[/api/ai-home-config body]:")
print(out.read().decode("utf-8", "ignore"))
ssh.close()
