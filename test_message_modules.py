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
    CONTAINER = f"{DEPLOY_ID}-backend"

    results = []

    # Check admin login endpoint format
    results.append("=" * 60)
    results.append("Check admin.py login details")
    results.append("=" * 60)
    out, _ = ssh_exec(client, f'docker exec {CONTAINER} grep -A 20 "def admin_login\\|def login\\|@router.post.*login" /app/app/api/admin.py 2>&1', timeout=30)
    results.append(out)

    # Also check init_data for default admin user
    results.append("\n--- Check init_data for admin credentials ---")
    out, _ = ssh_exec(client, f'docker exec {CONTAINER} grep -A 10 "admin\\|password\\|phone" /app/app/init_data.py 2>&1 | head -60', timeout=30)
    results.append(out)

    # Try admin login with different credentials
    results.append("\n" + "=" * 60)
    results.append("Try admin login endpoint")
    results.append("=" * 60)

    login_attempts = [
        ('{"username":"admin","password":"admin123"}', "username/admin123"),
        ('{"phone":"admin","password":"admin123"}', "phone=admin/admin123"),
        ('{"username":"admin","password":"admin"}', "username/admin"),
        ('{"phone":"13800000000","password":"admin123"}', "phone=13800000000/admin123"),
    ]

    for body, desc in login_attempts:
        cmd = f"""curl -s -w "\\nHTTP_CODE:%{{http_code}}" -X POST {BASE_URL}/api/admin/login -H "Content-Type: application/json" -d '{body}'"""
        out, _ = ssh_exec(client, cmd, timeout=30)
        results.append(f"\n--- {desc} ---")
        results.append(out)

    # Check what the admin login expects (read the schema)
    results.append("\n" + "=" * 60)
    results.append("Check admin login schema")
    results.append("=" * 60)
    out, _ = ssh_exec(client, f'docker exec {CONTAINER} grep -B 5 -A 30 "admin.*login\\|AdminLogin\\|class.*Login" /app/app/schemas/admin.py 2>&1', timeout=30)
    results.append(out)

    # Check openapi spec for admin login
    results.append("\n--- OpenAPI for admin login ---")
    cmd = f'curl -s {BASE_URL}/openapi.json | python3 -c "import sys,json; d=json.load(sys.stdin); p=d.get(\'paths\',{{}}).get(\'/api/admin/login\',{{}}); print(json.dumps(p, indent=2, ensure_ascii=False))"'
    out, _ = ssh_exec(client, cmd, timeout=30)
    results.append(out)

    output = '\n'.join(results)
    print(output)

    client.close()

if __name__ == "__main__":
    main()
