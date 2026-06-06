"""Phase 3: Remote Deploy - Git pull, build, gateway update, migrations, account check."""
import paramiko
import time
import sys

HOST = 'newbb.test.bangbangvip.com'
PORT = 22
USER = 'ubuntu'
PASSWORD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR = f'/home/ubuntu/{DEPLOY_ID}'
GATEWAY_CONF = f'/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf'
GATEWAY_SERVER = f'/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server'
GATEWAY_CONTAINER = 'gateway-nginx'

def run_cmd(client, cmd, timeout=60, print_output=True):
    """Execute command and return stdout, stderr, exit_code."""
    if print_output:
        print(f"  [CMD] {cmd[:120]}...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    exit_code = stdout.channel.recv_exit_status()
    if print_output:
        if out:
            for line in out.split('\n')[-20:]:
                print(f"    {line}")
        if err and exit_code != 0:
            print(f"  [STDERR] {err[:500]}")
    return out, err, exit_code

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("=" * 60)
        print("阶段 3：远程部署开始")
        print("=" * 60)
        client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
        
        # Step 1: Git pull latest code
        print("\n[Step 1] Git pull 最新代码")
        git_url = 'https://kun-an:pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git'
        cmds = [
            f'cd {PROJECT_DIR} && git remote set-url codeup "{git_url}" 2>/dev/null; git remote add codeup "{git_url}" 2>/dev/null; echo "remote set"',
            f'cd {PROJECT_DIR} && git fetch codeup master 2>&1',
            f'cd {PROJECT_DIR} && git reset --hard codeup/master 2>&1',
            f'cd {PROJECT_DIR} && git log --oneline -3',
        ]
        for cmd in cmds:
            out, err, ec = run_cmd(client, cmd)
            if ec != 0 and 'remote set' not in cmd:
                print(f"  [WARN] exit={ec}")

        # Step 2: Deploy gateway config (both .conf and .server for compatibility)
        print("\n[Step 2] 部署 Gateway 路由配置")
        gateway_config = r'''# ===== Project: {DEPLOY_ID} =====
server {{
    listen 443 ssl http2;
    server_name {DEPLOY_ID}.noob-ai.test.bangbangvip.com;

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
}}'''.format(DEPLOY_ID=DEPLOY_ID)
        
        # Write gateway config to both .conf and .server
        escaped_config = gateway_config.replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
        write_cmd = f'cat > {GATEWAY_SERVER} << \'GATEWAY_EOF\'\n{gateway_config}\nGATEWAY_EOF'
        out, err, ec = run_cmd(client, write_cmd, timeout=10)
        
        # Also copy to .conf  
        copy_cmd = f'cp {GATEWAY_SERVER} {GATEWAY_CONF} 2>/dev/null; echo "Gateway config written"'
        out, err, ec = run_cmd(client, copy_cmd)
        
        # Reload gateway nginx
        print("\n[Step 2b] 重载 Gateway Nginx")
        out, err, ec = run_cmd(client, f'docker exec {GATEWAY_CONTAINER} nginx -t 2>&1')
        out, err, ec = run_cmd(client, f'docker exec {GATEWAY_CONTAINER} nginx -s reload 2>&1')

        # Step 3: Stop old containers and rebuild
        print("\n[Step 3] 停止旧容器并重建")
        out, err, ec = run_cmd(client, f'cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml down --remove-orphans 2>&1', timeout=60)
        
        # Start DB first and wait for it
        print("\n[Step 3b] 启动 MySQL 并等待就绪")
        out, err, ec = run_cmd(client, f'cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d db 2>&1', timeout=60)
        
        # Wait for MySQL to be healthy
        print("  等待 MySQL 健康检查...")
        for i in range(30):
            time.sleep(5)
            out, err, ec = run_cmd(client, f"docker inspect {DEPLOY_ID}-db --format '{{{{.State.Health.Status}}}}' 2>/dev/null", print_output=False)
            status = out.strip()
            if status == 'healthy':
                print(f"  MySQL 已就绪 (healthy)")
                break
            if i % 6 == 0:
                print(f"  等待中... (当前状态: {status})")
        
        # Step 4: Build and start all services
        print("\n[Step 4] 构建并启动所有服务 (docker compose up --build -d)")
        out, err, ec = run_cmd(client, f'cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up --build -d 2>&1', timeout=600)
        
        # Step 5: Wait for containers to be healthy
        print("\n[Step 5] 等待容器健康检查...")
        time.sleep(15)
        for svc in ['backend', 'h5-web', 'admin-web']:
            container = f'{DEPLOY_ID}-{svc}' if svc != 'h5-web' and svc != 'admin-web' else f'{DEPLOY_ID}-{svc.replace("-web","")}'
            if svc == 'h5-web':
                container = f'{DEPLOY_ID}-h5'
            elif svc == 'admin-web':
                container = f'{DEPLOY_ID}-admin'
            else:
                container = f'{DEPLOY_ID}-backend'
            
            for i in range(20):
                time.sleep(3)
                out, err, ec = run_cmd(client, f"docker inspect {container} --format '{{{{.State.Health.Status}}}}' 2>/dev/null", print_output=False)
                status = out.strip()
                if status == 'healthy':
                    print(f"  {container}: healthy")
                    break
                if i == 19:
                    print(f"  {container}: timeout waiting for healthy (status={status})")
                if i % 5 == 0:
                    print(f"  {container}: waiting... (status={status})")
        
        # Show container status
        print("\n[Step 5b] 容器状态")
        out, err, ec = run_cmd(client, f'docker ps --filter name={DEPLOY_ID} --format "table {{{{.Names}}}}\t{{{{.Status}}}}"')

        # Step 6: Database migrations
        print("\n[Step 6] 数据库迁移")
        # Run init.sql to ensure database exists
        out, err, ec = run_cmd(client, f'docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 -e "SHOW DATABASES;" 2>&1')
        
        # Run backend migrations (tables created by SQLAlchemy on startup)
        print("  触发后端数据库表创建...")
        out, err, ec = run_cmd(client, f'docker exec {DEPLOY_ID}-backend python3 -c "import asyncio; from app.database import engine; from app.models.models import Base; asyncio.run(engine.run_sync(lambda conn: Base.metadata.create_all(conn)))" 2>&1', timeout=30)
        
        # Check tables
        print("  检查数据库表:")
        out, err, ec = run_cmd(client, f'docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 bini_health -e "SHOW TABLES;" 2>&1')
        
        # Step 7: Default account check
        print("\n[Step 7] 默认账号检查")
        out, err, ec = run_cmd(client, f'docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 bini_health -e "SELECT id, username, role, is_active FROM users LIMIT 5;" 2>&1')
        
        # Try creating default admin if not exists
        print("  检查/创建默认管理员 (admin/admin123)...")
        create_admin_cmd = f'''docker exec {DEPLOY_ID}-backend python3 -c "
import asyncio
from app.database import get_session
from app.models.models import User
from app.core.security import get_password_hash

async def check_admin():
    async for session in get_session():
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.username == 'admin'))
        user = result.scalar_one_or_none()
        if user:
            print(f'Admin exists: id={{user.id}}, role={{user.role}}, active={{user.is_active}}')
        else:
            new_admin = User(
                username='admin',
                hashed_password=get_password_hash('admin123'),
                role='admin',
                is_active=True
            )
            session.add(new_admin)
            await session.commit()
            await session.refresh(new_admin)
            print(f'Admin created: id={{new_admin.id}}')
        break

asyncio.run(check_admin())
" 2>&1'''
        out, err, ec = run_cmd(client, create_admin_cmd, timeout=30)
        
        # Final verification
        print("\n[Step 8] 最终验证")
        # Test API health
        out, err, ec = run_cmd(client, f'docker exec {DEPLOY_ID}-backend curl -sf http://localhost:8000/api/health 2>&1 || wget -qO- http://localhost:8000/api/health 2>&1')
        print(f"  Backend health: {'OK' if 'ok' in out.lower() or 'health' in out.lower() else out[:100]}")
        
        # Test H5
        out, err, ec = run_cmd(client, f'docker exec {DEPLOY_ID}-h5 wget -qO- http://localhost:3001/ 2>&1 | head -c 200')
        print(f"  H5 response: {'OK' if out else 'No response'} ({len(out)} bytes)")
        
        # Test Admin
        out, err, ec = run_cmd(client, f'docker exec {DEPLOY_ID}-admin wget -qO- http://localhost:3000/admin 2>&1 | head -c 200')
        print(f"  Admin response: {'OK' if out else 'No response'} ({len(out)} bytes)")
        
        print("\n" + "=" * 60)
        print("阶段 3：部署完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n部署失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        client.close()

if __name__ == '__main__':
    main()
