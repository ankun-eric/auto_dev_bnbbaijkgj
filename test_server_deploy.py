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

    # Check router prefixes
    print("=" * 60)
    print("Check SMS router prefix")
    print("=" * 60)
    out, _ = ssh_exec(client, f'docker exec {CONTAINER} head -30 /app/app/api/sms.py 2>&1', timeout=30)
    print(out)

    print("\n--- Email Notify router ---")
    out, _ = ssh_exec(client, f'docker exec {CONTAINER} head -30 /app/app/api/email_notify.py 2>&1', timeout=30)
    print(out)

    print("\n--- WeChat Push router ---")
    out, _ = ssh_exec(client, f'docker exec {CONTAINER} head -30 /app/app/api/wechat_push.py 2>&1', timeout=30)
    print(out)

    # List ALL routes properly
    print("\n" + "=" * 60)
    print("List ALL routes (skip websocket)")
    print("=" * 60)
    out, _ = ssh_exec(client, f"""docker exec {CONTAINER} python -c "
from app.main import app
for r in app.routes:
    methods = getattr(r, 'methods', None)
    if methods:
        print(r.path, methods)
    else:
        print(r.path, '(mount/ws)')
" 2>&1""", timeout=30)
    print(out)

    # Find registered admin user
    print("\n" + "=" * 60)
    print("Check init_data for default users")
    print("=" * 60)
    out, _ = ssh_exec(client, f'docker exec {CONTAINER} cat /app/app/init_data.py 2>&1', timeout=30)
    print(out)

    # Check gateway nginx config
    print("\n" + "=" * 60)
    print("Check gateway-nginx config for this project")
    print("=" * 60)
    out, _ = ssh_exec(client, f'docker exec gateway-nginx cat /etc/nginx/conf.d/autodev.conf 2>&1 | head -100', timeout=30)
    print(out)

    # Check project's own nginx or docker-compose
    print("\n" + "=" * 60)
    print("Check docker containers for this project")
    print("=" * 60)
    out, _ = ssh_exec(client, f'docker ps --format "table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}" | grep {DEPLOY_ID} 2>&1', timeout=30)
    print(out)

    client.close()

if __name__ == "__main__":
    main()
