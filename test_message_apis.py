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
    client.connect("newbb.bangbangvip.com", port=22, username="ubuntu", password="Newbang888", timeout=30)

    DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
    CONTAINER = f"{DEPLOY_ID}-backend"

    # Check if message routers exist in the codebase
    print("=" * 60)
    print("Check for SMS/WeChat/Email router files")
    print("=" * 60)
    out, _ = ssh_exec(client, f'docker exec {CONTAINER} find /app -name "*.py" | sort 2>&1', timeout=30)
    print(out)

    # Check main.py for router includes
    print("\n" + "=" * 60)
    print("Check main.py router registrations")
    print("=" * 60)
    out, _ = ssh_exec(client, f'docker exec {CONTAINER} cat /app/app/main.py 2>&1', timeout=30)
    print(out)

    # Check DB config module
    print("\n" + "=" * 60)
    print("Check database module location")
    print("=" * 60)
    out, _ = ssh_exec(client, f'docker exec {CONTAINER} find /app -name "database*" -o -name "db*" | head -20 2>&1', timeout=30)
    print(out)

    # Try to find users
    print("\n" + "=" * 60)
    print("Check users in database")
    print("=" * 60)
    out, _ = ssh_exec(client, f"""docker exec {CONTAINER} python -c "
from app.core.database import SessionLocal
from app.models.user import User
db = SessionLocal()
users = db.query(User).all()
for u in users:
    print(f'id={{u.id}} phone={{u.phone}} role={{getattr(u, \"role\", \"N/A\")}}')
db.close()
" 2>&1""", timeout=30)
    print(out)

    # Alternative: check db session module name
    print("\n" + "=" * 60)
    print("Check for db session import pattern")
    print("=" * 60)
    out, _ = ssh_exec(client, f'docker exec {CONTAINER} grep -r "SessionLocal\\|get_db\\|engine" /app/app/core/ --include="*.py" 2>&1 || docker exec {CONTAINER} grep -r "SessionLocal\\|get_db\\|engine" /app/app/ --include="*.py" -l 2>&1', timeout=30)
    print(out)

    client.close()

if __name__ == "__main__":
    main()
