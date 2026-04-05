import subprocess
import sys
import json

def ensure_paramiko():
    try:
        import paramiko
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "paramiko", "-q"], check=True)
    import paramiko
    return paramiko

def ssh_exec(client, cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    return out + err, exit_code

def main():
    paramiko = ensure_paramiko()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("newbb.test.bangbangvip.com", port=22, username="ubuntu", password="Bangbang987", timeout=30)

    DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
    BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

    results = []

    # Step 1: Health check
    results.append("=" * 60)
    results.append("1. API Health Check")
    results.append("=" * 60)
    out, _ = ssh_exec(client, f'curl -s -w "\\nHTTP_CODE:%{{http_code}}" {BASE_URL}/api/health', timeout=30)
    results.append(out)

    # Step 2: Admin login
    results.append("\n" + "=" * 60)
    results.append("2. Admin Login")
    results.append("=" * 60)
    login_cmd = f"""curl -s -w "\\nHTTP_CODE:%{{http_code}}" -X POST {BASE_URL}/api/admin/login -H "Content-Type: application/json" -d '{{"phone":"13800000000","password":"admin123"}}'"""
    out, _ = ssh_exec(client, login_cmd, timeout=30)
    results.append(out)

    token = ""
    try:
        lines = out.strip().split('\n')
        body_lines = [l for l in lines if not l.startswith('HTTP_CODE:')]
        body = '\n'.join(body_lines)
        login_data = json.loads(body.strip())
        token = login_data.get("token", "")
        if token:
            results.append(f"Token: {token[:40]}...")
    except Exception as e:
        results.append(f"Login parse error: {e}")

    # Step 3: Test API endpoints with correct paths
    results.append("\n" + "=" * 60)
    results.append("3. API Endpoint Tests (correct paths: /api/admin/...)")
    results.append("=" * 60)

    api_endpoints = [
        ("/api/admin/sms/config", "SMS Config"),
        ("/api/admin/sms/templates", "SMS Templates"),
        ("/api/admin/sms/logs", "SMS Logs"),
        ("/api/admin/wechat-push/config", "WeChat Push Config"),
        ("/api/admin/email-notify/config", "Email Notify Config"),
        ("/api/admin/email-notify/logs", "Email Notify Logs"),
    ]

    for path, name in api_endpoints:
        auth = f'-H "Authorization: Bearer {token}"' if token else ''
        cmd = f'curl -s -w "\\nHTTP_CODE:%{{http_code}}" {auth} {BASE_URL}{path}'
        out, _ = ssh_exec(client, cmd, timeout=30)
        results.append(f"\n--- {name} ({path}) ---")
        results.append(out)

    # Step 4: Also test original paths from test spec (for comparison)
    results.append("\n" + "=" * 60)
    results.append("4. Test original spec paths (expected 404)")
    results.append("=" * 60)

    original_paths = [
        ("/api/sms/config", "SMS Config (original)"),
        ("/api/sms/templates", "SMS Templates (original)"),
        ("/api/wechat-push/config", "WeChat Push Config (original)"),
        ("/api/email-notify/config", "Email Notify Config (original)"),
    ]

    for path, name in original_paths:
        auth = f'-H "Authorization: Bearer {token}"' if token else ''
        cmd = f'curl -s -o /dev/null -w "%{{http_code}}" {auth} {BASE_URL}{path}'
        out, _ = ssh_exec(client, cmd, timeout=15)
        results.append(f"{name}: HTTP {out.strip()}")

    # Step 5: Frontend page accessibility
    results.append("\n" + "=" * 60)
    results.append("5. Frontend Page Accessibility")
    results.append("=" * 60)

    pages = [
        ("/admin/", "Admin Dashboard"),
        ("/admin/sms", "SMS Admin (no trailing /)"),
        ("/admin/sms/", "SMS Admin (with trailing /)"),
        ("/admin/wechat-push", "WeChat Push Admin (no trailing /)"),
        ("/admin/wechat-push/", "WeChat Push Admin (with trailing /)"),
        ("/admin/email-notify", "Email Notify Admin (no trailing /)"),
        ("/admin/email-notify/", "Email Notify Admin (with trailing /)"),
    ]

    for path, name in pages:
        cmd = f'curl -s -o /dev/null -w "%{{http_code}}" -L {BASE_URL}{path}'
        out, _ = ssh_exec(client, cmd, timeout=15)
        results.append(f"{name}: HTTP {out.strip()}")

    # Step 6: User auth login test
    results.append("\n" + "=" * 60)
    results.append("6. User Auth Login (/api/auth/login)")
    results.append("=" * 60)
    login_cmd2 = f"""curl -s -w "\\nHTTP_CODE:%{{http_code}}" -X POST {BASE_URL}/api/auth/login -H "Content-Type: application/json" -d '{{"phone":"13800000000","password":"admin123"}}'"""
    out, _ = ssh_exec(client, login_cmd2, timeout=30)
    results.append(out)

    client.close()

    results.append("\n" + "=" * 60)
    results.append("ALL TESTS COMPLETED")
    results.append("=" * 60)

    output = '\n'.join(results)
    with open("test_results_final.txt", "w", encoding="utf-8") as f:
        f.write(output)
    print(output)

if __name__ == "__main__":
    main()
