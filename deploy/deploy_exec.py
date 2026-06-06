"""Stage 3: Remote deployment executor."""
import paramiko
import time
import sys
import os

HOST = "134.175.97.26"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"
GIT_URL = "https://codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"
GIT_USER = "kun-an"
GIT_TOKEN = "pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"
ACR_ADDR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"

def ssh_connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=60)
    return ssh

def run(ssh, cmd, timeout=120, desc=""):
    print(f"\n>>> [{desc}] {cmd[:120]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-2000:] if len(out) > 2000 else out)
    if err:
        print("STDERR:", err[-500:] if len(err) > 500 else err)
    print(f"exit={code}")
    return out, err, code

def main():
    ssh = ssh_connect()
    print("=== SSH Connected ===")
    
    # ── Step 1: ACR Login ──
    run(ssh, f"docker login --username={ACR_USER} --password={ACR_PASS} {ACR_ADDR}", 
        desc="ACR Login")
    
    # ── Step 2: Git fetch latest code ──
    auth_url = GIT_URL.replace("https://", f"https://{GIT_USER}:{GIT_TOKEN}@")
    
    # Check if project dir exists
    out, _, _ = run(ssh, f"test -d {PROJECT_DIR} && echo EXISTS || echo NOT_EXISTS", desc="Check project dir")
    
    if "EXISTS" in out:
        # Existing deployment - git fetch + reset
        print("\n--- Existing deployment, updating code ---")
        run(ssh, f"cd {PROJECT_DIR} && git remote set-url origin {auth_url}", desc="Set git remote")
        run(ssh, f"cd {PROJECT_DIR} && git fetch --depth 1 origin 2>&1 || echo FETCH_FAILED", desc="Git fetch")
        run(ssh, f"cd {PROJECT_DIR} && git reset --hard origin/master 2>&1 || git reset --hard origin/main 2>&1", desc="Git reset")
        run(ssh, f"cd {PROJECT_DIR} && git clean -fd 2>&1", desc="Git clean")
    else:
        # Fresh clone
        print("\n--- Fresh clone ---")
        run(ssh, f"git clone --depth 1 --single-branch {auth_url} {PROJECT_DIR}", timeout=120, desc="Git clone")
    
    # Verify git
    out, _, _ = run(ssh, f"cd {PROJECT_DIR} && git log -1 --oneline && git status", desc="Git status")

    # ── Step 3: BUILD_COMMIT ──
    out, _, _ = run(ssh, f"cd {PROJECT_DIR} && git log -1 --format='%H' 2>/dev/null || echo 'unknown'", desc="Get BUILD_COMMIT")
    build_commit = out.strip().split('\n')[-1] if out.strip() else "unknown"
    # Remove any leading/trailing quotes
    build_commit = build_commit.strip("'\"")
    print(f"BUILD_COMMIT={build_commit}")
    
    # Write .env file with BUILD_COMMIT
    run(ssh, f"cd {PROJECT_DIR} && echo 'BUILD_COMMIT={build_commit}' > .env.production", desc="Write .env.production")
    
    # ── Step 4: Docker compose build ──
    print("\n=== Building Docker images ===")
    out, err, code = run(ssh, 
        f"cd {PROJECT_DIR} && BUILD_COMMIT={build_commit} docker compose -f docker-compose.prod.yml build --pull 2>&1",
        timeout=600, desc="Docker compose build")
    
    if code != 0:
        print("Build with --pull failed, retrying without --pull...")
        run(ssh,
            f"cd {PROJECT_DIR} && BUILD_COMMIT={build_commit} docker compose -f docker-compose.prod.yml build 2>&1",
            timeout=600, desc="Docker compose build (no pull)")
    
    # ── Step 5: Stop old containers and start new ──
    print("\n=== Restarting containers ===")
    run(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml down 2>&1 || true", desc="Docker compose down")
    run(ssh, f"cd {PROJECT_DIR} && BUILD_COMMIT={build_commit} docker compose -f docker-compose.prod.yml up -d 2>&1",
        timeout=300, desc="Docker compose up")
    
    # ── Step 6: Wait for health checks ──
    print("\n=== Waiting for health checks ===")
    max_wait = 24
    for i in range(max_wait):
        time.sleep(5)
        out, _, _ = run(ssh,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null",
            desc=f"Health check {i+1}/{max_wait}")
        if 'healthy' in out.lower():
            # Count healthy vs total
            total = out.count('"Name"')
            healthy = out.lower().count('"healthy"')
            print(f"  [{i+1}/{max_wait}] {healthy}/{total} containers healthy")
            if healthy >= total and total > 0:
                print("All containers healthy!")
                break
        else:
            print(f"  [{i+1}/{max_wait}] waiting...")
    else:
        print("WARNING: Health check timeout, checking status...")
        run(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps", desc="Container status")

    # ── Step 7: Connect gateway to project network ──
    run(ssh, f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>&1 || echo 'already connected'", 
        desc="Connect gateway to network")
    
    # ── Step 8: Gateway config check and reload ──
    print("\n=== Gateway config check ===")
    # Verify the .server file exists
    run(ssh, f"test -f /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server && echo 'SERVER_FILE_OK' || echo 'MISSING'",
        desc="Check .server file")
    
    # Test nginx config
    out, err, code = run(ssh, "docker exec gateway-nginx nginx -t 2>&1", desc="Nginx config test")
    if code != 0:
        print("ERROR: nginx config test failed!")
        # Try to recover
        run(ssh, "docker exec gateway-nginx nginx -t 2>&1", desc="Nginx config test (retry)")
    
    # Reload nginx
    run(ssh, "docker exec gateway-nginx nginx -s reload 2>&1", desc="Nginx reload")
    
    time.sleep(3)
    
    # ── Step 9: Verify SSL ──
    print("\n=== SSL Verification ===")
    run(ssh, f"curl -vI https://{DOMAIN}/api/health 2>&1 | head -30", desc="SSL health check")
    
    # ── Step 10: Database migration ──
    print("\n=== Database migration ===")
    run(ssh,
        f"docker exec -i {DEPLOY_ID}-backend sh -c 'cat > /tmp/db_migrate.py && cd /app && python /tmp/db_migrate.py' << 'PYEOF'\n"
        "import asyncio\n"
        "from app.core.database import engine, Base\n"
        "async def check():\n"
        "    async with engine.begin() as conn:\n"
        "        await conn.run_sync(Base.metadata.create_all)\n"
        "        print('create_all done')\n"
        "asyncio.run(check())\n"
        "PYEOF",
        timeout=120, desc="DB create_all")
    
    # Verify database tables
    run(ssh,
        f"docker exec -i {DEPLOY_ID}-backend sh -c 'cat > /tmp/db_list.py && cd /app && python /tmp/db_list.py' << 'PYEOF'\n"
        "import asyncio\n"
        "from app.core.database import engine\n"
        "from sqlalchemy import text\n"
        "async def list_tables():\n"
        "    async with engine.connect() as conn:\n"
        "        result = await conn.execute(text('SHOW TABLES'))\n"
        "        tables = [r[0] for r in result.fetchall()]\n"
        "        print(f'Total tables: {len(tables)}')\n"
        "        for t in sorted(tables)[:20]: print(f'  {t}')\n"
        "asyncio.run(list_tables())\n"
        "PYEOF",
        timeout=60, desc="List DB tables")

    # ── Step 11: Check admin user ──
    print("\n=== Admin user check ===")
    out, _, _ = run(ssh,
        f"docker exec -i {DEPLOY_ID}-backend sh -c 'cat > /tmp/check_admin.py && cd /app && python /tmp/check_admin.py' << 'PYEOF'\n"
        "import asyncio\n"
        "from app.core.database import async_session\n"
        "from sqlalchemy import text\n"
        "async def check_admin():\n"
        "    async with async_session() as db:\n"
        "        r = await db.execute(text(\"SELECT id, phone, nickname, role FROM users WHERE role='admin' LIMIT 1\"))\n"
        "        row = r.fetchone()\n"
        "        if row:\n"
        "            print(f'Admin exists: id={row[0]}, phone={row[1]}, nickname={row[2]}, role={row[3]}')\n"
        "        else:\n"
        "            print('NO_ADMIN')\n"
        "asyncio.run(check_admin())\n"
        "PYEOF",
        timeout=30, desc="Check admin user")
    
    if "NO_ADMIN" in out:
        print("Creating default admin user...")
        run(ssh,
            f"docker exec -i {DEPLOY_ID}-backend sh -c 'cat > /tmp/create_admin.py && cd /app && python /tmp/create_admin.py' << 'PYEOF'\n"
            "import asyncio\n"
            "from app.core.database import async_session\n"
            "from app.models.models import User, UserRole\n"
            "from app.core.security import get_password_hash\n"
            "from sqlalchemy import select\n"
            "async def create_admin():\n"
            "    async with async_session() as db:\n"
            "        r = await db.execute(select(User).where(User.role == UserRole.admin))\n"
            "        user = r.scalar_one_or_none()\n"
            "        if not user:\n"
            "            db.add(User(phone='13800000000', nickname='admin', password_hash=get_password_hash('admin123'), role=UserRole.admin, is_superuser=True))\n"
            "            await db.commit()\n"
            "            print('Admin created: admin/admin123')\n"
            "        else:\n"
            "            print('Admin already exists')\n"
            "asyncio.run(create_admin())\n"
            "PYEOF",
            timeout=30, desc="Create admin user")
    
    # ── Step 12: Final verification ──
    print("\n=== Final Verification ===")
    run(ssh, f"curl -s https://{DOMAIN}/api/health 2>&1", desc="Health endpoint")
    run(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps", desc="Container status")
    
    # BUILD_INFO verification
    run(ssh,
        f"docker exec {DEPLOY_ID}-backend cat /app/BUILD_INFO 2>/dev/null || echo 'no BUILD_INFO'",
        desc="BUILD_INFO check")
    
    print("\n\n===== DEPLOYMENT COMPLETE =====")
    print(f"Domain: https://{DOMAIN}")
    print(f"API: https://{DOMAIN}/api/health")
    print(f"Admin: https://{DOMAIN}/admin/")
    print(f"H5: https://{DOMAIN}/")
    print(f"Admin account: admin / admin123")
    
    ssh.close()

if __name__ == "__main__":
    main()
