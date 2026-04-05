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

def ssh_exec(client, cmd, timeout=180):
    """Execute command via SSH and return output + exit code."""
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
    
    results = []
    DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
    BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    CONTAINER = f"{DEPLOY_ID}-backend"

    # Step 1: Install pytest in container
    results.append("=" * 60)
    results.append("STEP 1: Install pytest in backend container")
    results.append("=" * 60)
    out, rc = ssh_exec(client, f"docker exec {CONTAINER} pip install pytest -q 2>&1", timeout=180)
    results.append(out)
    results.append(f"Exit code: {rc}")

    # Step 2: Run pytest
    results.append("")
    results.append("=" * 60)
    results.append("STEP 2: Running pytest")
    results.append("=" * 60)
    out, rc = ssh_exec(client, f"docker exec {CONTAINER} python -m pytest tests/test_message_modules.py -v --tb=short 2>&1", timeout=180)
    results.append(out)
    results.append(f"Exit code: {rc}")

    # If test file not found, check what test files exist
    if rc != 0 and ("no tests ran" in out.lower() or "not found" in out.lower() or "ERROR" in out):
        results.append("\n--- Checking available test files ---")
        out2, _ = ssh_exec(client, f"docker exec {CONTAINER} find /app -name 'test_*.py' -o -name '*_test.py' 2>&1", timeout=30)
        results.append(out2)
        
        out3, _ = ssh_exec(client, f"docker exec {CONTAINER} ls -la /app/tests/ 2>&1", timeout=30)
        results.append(out3)

    # Step 3: API Health
    results.append("")
    results.append("=" * 60)
    results.append("STEP 3: API Health Check")
    results.append("=" * 60)
    out, rc = ssh_exec(client, f'curl -s -w "\\nHTTP_CODE:%{{http_code}}" {BASE_URL}/api/health', timeout=30)
    results.append(out)

    # Step 4: Login
    results.append("")
    results.append("=" * 60)
    results.append("STEP 4: Login and get token")
    results.append("=" * 60)
    login_cmd = f"""curl -s -w "\\nHTTP_CODE:%{{http_code}}" -X POST {BASE_URL}/api/auth/login -H "Content-Type: application/json" -d '{{"username":"admin","password":"admin123"}}'"""
    out, rc = ssh_exec(client, login_cmd, timeout=30)
    results.append(out)

    token = ""
    try:
        lines = out.strip().split('\n')
        body = '\n'.join(l for l in lines if not l.startswith('HTTP_CODE:'))
        login_data = json.loads(body.strip())
        token = login_data.get("access_token", "")
        if token:
            results.append(f"Token obtained: {token[:30]}...")
        else:
            results.append(f"No access_token in response: {login_data}")
    except Exception as e:
        results.append(f"Failed to parse login response: {e}")

    # Step 5: API Endpoint Tests
    results.append("")
    results.append("=" * 60)
    results.append("STEP 5: API Endpoint Tests (with auth)")
    results.append("=" * 60)
    
    api_endpoints = [
        ("/api/sms/config", "SMS Config"),
        ("/api/sms/templates", "SMS Templates"),
        ("/api/sms/logs", "SMS Logs"),
        ("/api/wechat-push/config", "WeChat Push Config"),
        ("/api/email-notify/config", "Email Notify Config"),
        ("/api/email-notify/logs", "Email Notify Logs"),
    ]

    for path, name in api_endpoints:
        auth_header = f'-H "Authorization: Bearer {token}"' if token else ''
        cmd = f'curl -s -w "\\nHTTP_CODE:%{{http_code}}" {auth_header} {BASE_URL}{path}'
        out, rc = ssh_exec(client, cmd, timeout=30)
        results.append(f"\n--- {name} ({path}) ---")
        results.append(out)

    # Step 6: Frontend Page Accessibility
    results.append("")
    results.append("=" * 60)
    results.append("STEP 6: Frontend Page Accessibility")
    results.append("=" * 60)
    
    pages = [
        ("/admin/", "Admin Dashboard"),
        ("/admin/sms", "SMS Admin"),
        ("/admin/wechat-push", "WeChat Push Admin"),
        ("/admin/email-notify", "Email Notify Admin"),
    ]

    for path, name in pages:
        cmd = f'curl -s -o /dev/null -w "%{{http_code}}" {BASE_URL}{path}'
        out, rc = ssh_exec(client, cmd, timeout=30)
        results.append(f"{name} ({path}): HTTP {out.strip()}")

    client.close()

    results.append("")
    results.append("=" * 60)
    results.append("ALL TESTS COMPLETED")
    results.append("=" * 60)

    output = '\n'.join(results)
    with open("test_results.txt", "w", encoding="utf-8") as f:
        f.write(output)
    print(output)

if __name__ == "__main__":
    main()
