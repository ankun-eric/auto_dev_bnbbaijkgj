import paramiko, time

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    return out, err, code

PROD_DOMAIN = "https://chat.benne-ai.com"

urls = [
    ("GET /", f"{PROD_DOMAIN}/"),
    ("GET /api/health", f"{PROD_DOMAIN}/api/health"),
    ("GET /admin/", f"{PROD_DOMAIN}/admin/"),
    ("GET /api/docs", f"{PROD_DOMAIN}/api/docs"),
    ("GET /api/auth/login", f"{PROD_DOMAIN}/api/auth/login"),
]

print("=== 链接可达性检查 ===")
results = []
for label, url in urls:
    out, err, code = run(f"curl -sk -o /dev/null -w '%{{http_code}}' {url} 2>&1", timeout=15)
    http_code = out.strip()
    status = "OK" if http_code and http_code[0] in "23" else "FAIL"
    results.append((label, url, http_code, status))
    print(f"  {status}: {label} -> {http_code}")

# Summary
total = len(results)
ok_count = sum(1 for r in results if r[3] == "OK")
print(f"\n=== 检查汇总: {ok_count}/{total} 可达 ===")

failed = [r for r in results if r[3] == "FAIL"]
if failed:
    print("不可达链接:")
    for r in failed:
        print(f"  {r[3]}: {r[0]} ({r[1]}) -> {r[2]}")

# Also check APP detection
print("\n=== APP 端检测 ===")
out, err, code = run(f"ls /home/ubuntu/{DEPLOY_ID}/flutter_app/ 2>/dev/null | head -5 || echo 'NO_FLUTTER'")
if "NO_FLUTTER" not in out:
    print("  项目包含 flutter_app (APP端)")
    out, err, code = run(f"ls /home/ubuntu/{DEPLOY_ID}/flutter_app/android/ 2>/dev/null | head -3 || echo 'NO_ANDROID'")
    print(f"  Android: {'YES' if 'NO_ANDROID' not in out else 'NO'}")
    out, err, code = run(f"ls /home/ubuntu/{DEPLOY_ID}/flutter_app/ios/ 2>/dev/null | head -3 || echo 'NO_IOS'")
    print(f"  iOS: {'YES' if 'NO_IOS' not in out else 'NO'}")
else:
    print("  项目不包含 APP 端")

client.close()
print("\n=== 检查完成 ===")
