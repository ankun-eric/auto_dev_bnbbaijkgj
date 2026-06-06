#!/usr/bin/env python3
"""Phase 3: Remote deployment via SSH."""
import paramiko
import time
import sys
import os

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY_CONF = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
GATEWAY_CONTAINER = "gateway-nginx"
NETWORK_NAME = f"{DEPLOY_ID}-network"
PROJECT_DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"

ACR_REGISTRY = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"

GIT_REPO = "https://codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"
GIT_USER = "kun-an"
GIT_TOKEN = "pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74"

GIT_URL = f"https://{GIT_USER}:{GIT_TOKEN}@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/{DEPLOY_ID}.git"

DB_PASSWORD = "bini_health_2026"
DB_NAME = "bini_health"


class DeployRunner:
    def __init__(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.log_lines = []

    def log(self, msg):
        self.log_lines.append(msg)
        print(msg)

    def connect(self):
        self.log("[1/8] Connecting to server...")
        self.ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
        self.log("[OK] SSH connected")

    def run(self, cmd, timeout=60):
        """Execute command and return stdout, stderr, exit_code."""
        stdin, stdout, stderr = self.ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace').strip()
        err = stderr.read().decode('utf-8', errors='replace').strip()
        ec = stdout.channel.recv_exit_status()
        return out, err, ec

    def step_git_pull(self):
        self.log("\n[2/8] Git pull latest code...")
        # Check if project dir exists
        out, err, ec = self.run(f"test -d {PROJECT_DIR} && echo EXISTS || echo NOT_FOUND")
        if "NOT_FOUND" in out:
            self.log(f"  Cloning to {PROJECT_DIR}...")
            clone_cmd = f"git clone {GIT_URL} {PROJECT_DIR}"
            out, err, ec = self.run(clone_cmd, timeout=120)
            self.log(f"  Clone: {out[:200]} {err[:200]}")
        else:
            self.log(f"  Directory exists, fetching...")
            out, err, ec = self.run(f"cd {PROJECT_DIR} && git fetch origin && git reset --hard origin/master 2>&1", timeout=60)
            self.log(f"  Fetch: {out[:200]} {err[:200]}")

    def step_acr_login(self):
        self.log("\n[3/8] ACR login...")
        out, err, ec = self.run(f"echo '{ACR_PASS}' | docker login --username {ACR_USER} --password-stdin {ACR_REGISTRY} 2>&1")
        if "Login Succeeded" in out:
            self.log("  [OK] ACR login succeeded")
        else:
            self.log(f"  ACR login: {out} {err}")

    def step_docker_compose_up(self):
        self.log("\n[4/8] Docker compose build & up...")
        # Copy updated configs to server first
        deploy_dir = os.path.join(os.path.dirname(__file__), '')
        self.log(f"  Local deploy dir: {deploy_dir}")
        
        # Check what's running
        out, err, ec = self.run(f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps --format '{{{{.Names}}}} {{{{.Status}}}}' 2>&1")
        self.log(f"  Current compose status: {out[:500]}")
        
        # Check if docker-compose.prod.yml exists, if not use deploy/docker-compose.prod.yml
        out, err, ec = self.run(f"test -f {PROJECT_DIR}/docker-compose.prod.yml && echo EXISTS || echo NOT_FOUND")
        if "NOT_FOUND" in out:
            self.log("  docker-compose.prod.yml NOT FOUND in project root, checking deploy/")
            out2, _, _ = self.run(f"test -f {PROJECT_DIR}/deploy/docker-compose.prod.yml && echo EXISTS || echo NOT_FOUND")
            if "EXISTS" in out2:
                self.log("  Found in deploy/, will use deploy/docker-compose.prod.yml")
                self.compose_file = "deploy/docker-compose.prod.yml"
                self.build_context = "deploy"
            else:
                self.log("  [WARN] No compose file found!")
                self.compose_file = None
        else:
            self.compose_file = "docker-compose.prod.yml"
            self.build_context = "."
        
        self.log(f"  Using compose file: {PROJECT_DIR}/{self.compose_file}")
    
    def step_health_check(self):
        self.log("\n[5/8] Health check...")
        containers = [
            f"{DEPLOY_ID}-backend",
            f"{DEPLOY_ID}-h5", 
            f"{DEPLOY_ID}-admin",
            f"{DEPLOY_ID}-db",
        ]
        for c in containers:
            out, err, ec = self.run(f"docker inspect {c} --format '{{{{.State.Status}}}} {{{{.State.Health.Status}}}}' 2>/dev/null || echo NOT_FOUND")
            self.log(f"  {c}: {out}")
    
    def step_gateway_config(self):
        self.log("\n[6/8] Gateway config update...")
        
        # Read local gateway config
        local_conf_path = os.path.join(os.path.dirname(__file__), 'gateway-routes.conf')
        if not os.path.exists(local_conf_path):
            local_conf_path = os.path.join(os.path.dirname(__file__), '..', 'gateway-routes.conf')
        
        if not os.path.exists(local_conf_path):
            self.log(f"  [WARN] Local gateway config not found at {local_conf_path}")
            # Use built-in config
            conf_content = self.get_gateway_conf_content()
        else:
            with open(local_conf_path, 'r', encoding='utf-8') as f:
                conf_content = f.read()
        
        self.log(f"  Config length: {len(conf_content)} bytes")
        
        # Write config to server
        escaped = conf_content.replace("'", "'\\''")
        # Use base64 to avoid escaping issues
        import base64
        b64 = base64.b64encode(conf_content.encode()).decode()
        out, err, ec = self.run(f"echo '{b64}' | base64 -d > /tmp/{DEPLOY_ID}.conf")
        if ec != 0:
            self.log(f"  [ERROR] Failed to write temp config: {err}")
            return
        
        # Copy to gateway conf.d via docker cp or direct write
        # First ensure gateway conf.d dir exists on host
        out, err, ec = self.run(f"test -d /home/ubuntu/gateway/conf.d && echo EXISTS || echo NOT_FOUND")
        if "NOT_FOUND" in out:
            self.log("  Creating /home/ubuntu/gateway/conf.d/")
            self.run("mkdir -p /home/ubuntu/gateway/conf.d")
        
        # Copy to host gateway conf.d
        self.run(f"cp /tmp/{DEPLOY_ID}.conf {GATEWAY_CONF}")
        self.log(f"  Written to {GATEWAY_CONF}")
        
        # Copy into gateway container
        out, err, ec = self.run(f"docker cp /tmp/{DEPLOY_ID}.conf {GATEWAY_CONTAINER}:/etc/nginx/conf.d/{DEPLOY_ID}.conf 2>&1")
        self.log(f"  docker cp result: {out} {err}")
        
        # Test nginx config
        out, err, ec = self.run(f"docker exec {GATEWAY_CONTAINER} nginx -t 2>&1")
        self.log(f"  nginx -t: {out} {err}")
        
        if ec != 0:
            self.log(f"  [ERROR] nginx config test failed!")
            return
        
        # Reload nginx
        out, err, ec = self.run(f"docker exec {GATEWAY_CONTAINER} nginx -s reload 2>&1")
        self.log(f"  nginx reload: {out} {err}")
        
        # Ensure gateway is on project network
        out, err, ec = self.run(f"docker network connect {NETWORK_NAME} {GATEWAY_CONTAINER} 2>&1")
        self.log(f"  network connect: {out} {err}")
    
    def get_gateway_conf_content(self):
        return f"""# ===== Project: {DEPLOY_ID} =====
server {{
    listen 443 ssl http2;
    server_name {PROJECT_DOMAIN};

    ssl_certificate     /etc/nginx/ssl/wildcard.noob-ai.test.bangbangvip.com.crt;
    ssl_certificate_key /etc/nginx/ssl/wildcard.noob-ai.test.bangbangvip.com.key;

    location /api/ {{
        resolver 127.0.0.11 valid=10s ipv6=off;
        set $backend {DEPLOY_ID}-backend;
        proxy_pass http://$backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
        proxy_buffering off;
        proxy_request_buffering off;
    }}

    location /uploads/ {{
        resolver 127.0.0.11 valid=10s ipv6=off;
        set $backend {DEPLOY_ID}-backend;
        proxy_pass http://$backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        expires 30d;
        add_header Cache-Control "public" always;
    }}

    location /admin/ {{
        resolver 127.0.0.11 valid=10s ipv6=off;
        set $admin {DEPLOY_ID}-admin;
        proxy_pass http://$admin:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }}

    location / {{
        resolver 127.0.0.11 valid=10s ipv6=off;
        set $h5 {DEPLOY_ID}-h5;
        proxy_pass http://$h5:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }}
}}"""
    
    def step_db_init(self):
        self.log("\n[7/8] Database initialization check...")
        # Check if DB is accessible via backend container
        out, err, ec = self.run(
            f"docker exec {DEPLOY_ID}-backend python3 -c \""
            f"from sqlalchemy import create_engine, text;"
            f"e=create_engine('mysql+pymysql://root:{DB_PASSWORD}@{DEPLOY_ID}-db:3306/{DB_NAME}');"
            f"r=e.execute(text('SELECT 1'));"
            f"print('DB_OK:', r.fetchone())\" 2>&1 || echo DB_CHECK_FAILED"
        , timeout=30)
        self.log(f"  DB connection check: {out[:200]}")
        
        # Try to run DB init via backend's models
        out, err, ec = self.run(
            f"docker exec {DEPLOY_ID}-backend python3 -c \""
            f"from app.database import engine, Base;"
            f"from app.models import *;"
            f"Base.metadata.create_all(bind=engine);"
            f"print('DB_INIT_DONE')\" 2>&1"
        , timeout=60)
        self.log(f"  DB init: {out[:300]} {err[:300]}")
    
    def step_default_account(self):
        self.log("\n[8/8] Default account check...")
        out, err, ec = self.run(
            f"docker exec {DEPLOY_ID}-backend python3 -c \""
            f"from sqlalchemy import create_engine, text;"
            f"e=create_engine('mysql+pymysql://root:{DB_PASSWORD}@{DEPLOY_ID}-db:3306/{DB_NAME}');"
            f"r=e.execute(text(\\\"SELECT username FROM users WHERE username='admin' LIMIT 1\\\"));"
            f"row=r.fetchone();"
            f"print('admin_exists:', row is not None)\" 2>&1 || echo ACCOUNT_CHECK_FAILED"
        , timeout=30)
        self.log(f"  Admin account check: {out[:200]}")
        
        # If no admin, try to create
        if "admin_exists: False" in out:
            self.log("  Creating default admin account...")
            out2, err2, ec2 = self.run(
                f"docker exec {DEPLOY_ID}-backend python3 -c \""
                f"from app.database import SessionLocal;"
                f"from app.models import User;"
                f"from passlib.context import CryptContext;"
                f"pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto');"
                f"db=SessionLocal();"
                f"try:"
                f"  u=User(username='admin', hashed_password=pwd_context.hash('admin123'), is_admin=True);"
                f"  db.add(u); db.commit(); print('ADMIN_CREATED')"
                f"except Exception as ex: print('ERR:', ex)"
                f"finally: db.close()\" 2>&1"
            , timeout=30)
            self.log(f"  Create admin: {out2[:200]} {err2[:200]}")
    
    def final_verify(self):
        self.log("\n[FINAL] Verification...")
        # Check health endpoint
        out, err, ec = self.run(
            f"docker exec {DEPLOY_ID}-backend curl -sf http://localhost:8000/api/health 2>&1 || echo HEALTH_FAILED"
        , timeout=15)
        self.log(f"  Backend health: {out[:200]}")
        
        # Check H5
        out, err, ec = self.run(
            f"docker exec {DEPLOY_ID}-h5 wget -qO- http://localhost:3001/ 2>&1 | head -c 200 || echo H5_FAILED"
        , timeout=15)
        self.log(f"  H5 check: {out[:200]}")
        
        # Check Admin
        out, err, ec = self.run(
            f"docker exec {DEPLOY_ID}-admin wget -qO- http://localhost:3000/admin/ 2>&1 | head -c 200 || echo ADMIN_FAILED"
        , timeout=15)
        self.log(f"  Admin check: {out[:200]}")
        
        # External check via gateway
        out, err, ec = self.run(
            f"curl -sk https://{PROJECT_DOMAIN}/api/health 2>&1 | head -c 200 || echo GATEWAY_CHECK_FAILED"
        , timeout=15)
        self.log(f"  Gateway external check: {out[:200]}")
    
    def run_all(self):
        try:
            self.connect()
            self.step_git_pull()
            self.step_acr_login()
            self.step_docker_compose_up()
            self.step_health_check()
            self.step_gateway_config()
            self.step_db_init()
            self.step_default_account()
            self.final_verify()
        except Exception as e:
            self.log(f"\n[FATAL] {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.ssh.close()
        
        # Write log
        with open(os.path.join(os.path.dirname(__file__), 'deploy_result.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.log_lines))
        
        print("\nDone. Log written to deploy/deploy_result.txt")
        return self.log_lines


if __name__ == "__main__":
    runner = DeployRunner()
    runner.run_all()
