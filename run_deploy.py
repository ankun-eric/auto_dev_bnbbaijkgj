"""
Full deployment script: pull from Codeup, build, deploy, verify.
"""
import paramiko
import time
import sys

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_CONF_SRC = f"{PROJECT_DIR}/gateway-routes.conf"
GATEWAY_CONF_DST = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server"
GATEWAY_CONTAINER = "gateway-nginx"
BUILD_COMMIT = "b0126a1cf95b8fe71b80f2f0d25c540c3e740a04"
DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"

RESULT_LOG = "C:/auto_output/bnbbaijkgj/deploy_result.txt"

def run(ssh, cmd, timeout=120):
    """Execute command via SSH and return stdout, stderr."""
    stdin, stdout, stderr = ssh.exec_command(f"cd {PROJECT_DIR} && {cmd}", timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

def log(f, msg):
    f.write(msg + "\n")
    print(msg, flush=True)

def main():
    with open(RESULT_LOG, 'w', encoding='utf-8') as f:
        log(f, "=" * 60)
        log(f, f"Deploy Start: DEPLOY_ID={DEPLOY_ID}")
        log(f, f"Domain: https://{DOMAIN}")
        log(f, "=" * 60)
        
        # Connect SSH
        log(f, "\n[1] Connecting to server...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)
            log(f, "    SSH connected OK")
        except Exception as e:
            log(f, "    SSH connection FAILED: {e}")
            return
        
        # ACR login
        log(f, "\n[2] ACR Login...")
        out, err = run(ssh, "echo 'xiaobai888' | docker login --username ankun888 --password-stdin crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com 2>&1")
        log(f, out if "succeeded" in out.lower() else f"{out} {err}")
        
        # Git pull
        log(f, "\n[3] Git pull from Codeup...")
        out, err = run(ssh, "git pull codeup master 2>&1", timeout=30)
        log(f, f"    {out[:300]}")
        if err:
            log(f, f"    stderr: {err[:200]}")
        
        # Stop old containers
        log(f, "\n[4] Stopping old containers...")
        out, err = run(ssh, "docker compose -f docker-compose.prod.yml down 2>&1", timeout=60)
        log(f, f"    {out[:200]}")
        
        # Build with no cache
        log(f, "\n[5] Building images (no-cache)...")
        log(f, f"    BUILD_COMMIT={BUILD_COMMIT}")
        out, err = run(ssh, f"BUILD_COMMIT={BUILD_COMMIT} docker compose -f docker-compose.prod.yml build --no-cache 2>&1", timeout=600)
        log(f, f"    Build output ({len(out)} chars)")
        if "error" in out.lower() or "error" in err.lower():
            log(f, "    Build errors (last 500):")
            combined = (out + "\n" + err)
            log(f, f"    {combined[-500:]}")
        
        # Start containers
        log(f, "\n[6] Starting containers...")
        out, err = run(ssh, "docker compose -f docker-compose.prod.yml up -d 2>&1", timeout=60)
        log(f, f"    {out[:300]}")
        
        # Wait for healthchecks
        log(f, "\n[7] Waiting for containers to be healthy...")
        all_healthy = False
        for i in range(30):
            time.sleep(10)
            out, err = run(ssh, "docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}' 2>&1", timeout=10)
            lines = out.strip().split('\n')
            healthy_count = sum(1 for l in lines if 'healthy' in l.lower() or 'Up' in l)
            log(f, f"    [{i+1}] {len(lines)} containers, {healthy_count} running: {lines}")
            if all('Up' in l for l in lines):
                all_healthy = True
                break
        
        if all_healthy:
            log(f, "    All containers are running!")
        else:
            log(f, "    WARNING: Not all containers healthy after 5 min wait")
        
        # Copy gateway config
        log(f, "\n[8] Updating gateway nginx config...")
        out, err = run(ssh, f"cp {GATEWAY_CONF_SRC} {GATEWAY_CONF_DST} 2>&1")
        log(f, f"    cp: {out} {err}")
        
        # Reload nginx
        log(f, "\n[9] Reloading gateway nginx...")
        out, err = run(ssh, f"docker exec {GATEWAY_CONTAINER} nginx -t 2>&1", timeout=10)
        log(f, f"    nginx -t: {out[:200]} {err[:200]}")
        
        out, err = run(ssh, f"docker exec {GATEWAY_CONTAINER} nginx -s reload 2>&1", timeout=10)
        log(f, f"    reload: {out[:200]} {err[:200]}")
        
        # Verify SSL
        log(f, "\n[10] Verifying HTTPS...")
        out, err = run(ssh, f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/health 2>&1", timeout=15)
        log(f, f"    /api/health -> HTTP {out}")
        
        out, err = run(ssh, f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/ 2>&1", timeout=15)
        log(f, f"    / (H5) -> HTTP {out}")
        
        out, err = run(ssh, f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/admin/ 2>&1", timeout=15)
        log(f, f"    /admin/ -> HTTP {out}")
        
        # Check default admin account
        log(f, "\n[11] Checking default admin account (admin/admin123)...")
        out, err = run(ssh, f"docker exec {DEPLOY_ID}-backend python -c \"import asyncio; from app.core.database import async_session; from app.models.models import User; from sqlalchemy import select; async def check(): async with async_session() as db: r = await db.execute(select(User).where(User.username == 'admin')); u = r.scalar_one_or_none(); print(f'admin exists={u is not None}, role={u.role if u else None}') if u else print('admin NOT FOUND'); asyncio.run(check())\" 2>&1", timeout=20)
        log(f, f"    {out[:300]}")
        
        # DB init check
        log(f, "\n[12] Checking database...")
        out, err = run(ssh, f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 -e 'SHOW DATABASES;' 2>&1 | head -5", timeout=10)
        log(f, f"    {out[:300]}")
        
        # Final status
        log(f, "\n[13] Final container status...")
        out, err = run(ssh, "docker ps --filter name=6b099ed3 --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'", timeout=10)
        log(f, f"    {out}")
        
        log(f, "\n" + "=" * 60)
        log(f, "Deployment Complete!")
        log(f, f"URL: https://{DOMAIN}")
        log(f, "=" * 60)
        
        ssh.close()

if __name__ == "__main__":
    main()
