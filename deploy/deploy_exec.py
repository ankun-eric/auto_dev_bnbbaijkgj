#!/usr/bin/env python3
"""Full deployment executor for noob-deploy skill."""
import paramiko
import sys
import time

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_DIR = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
GATEWAY_CONF = '/home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf'
GATEWAY_CONTAINER = 'gateway-nginx'
DOMAIN = '6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'


def get_ssh():
    """Create SSH connection."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run_cmd(ssh, cmd, timeout=120):
    """Execute command on remote server."""
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")
    print(f"[exit_code: {exit_code}]")
    return out, err, exit_code


def step1_check():
    """Step 1: Check server environment."""
    print("=" * 60)
    print("STEP 1: CHECK ENVIRONMENT")
    print("=" * 60)
    ssh = get_ssh()
    
    run_cmd(ssh, 'docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep -E "NAMES|6b099ed3" || echo "No matching containers"')
    run_cmd(ssh, 'docker network ls --filter name=6b099ed3 --format "{{.Name}}"')
    run_cmd(ssh, f'docker exec {GATEWAY_CONTAINER} cat /etc/nginx/nginx.conf 2>/dev/null | head -120 || echo "Cannot read nginx.conf"')
    run_cmd(ssh, f'docker exec {GATEWAY_CONTAINER} ls -la /etc/nginx/conf.d/ 2>/dev/null')
    run_cmd(ssh, f'cat {GATEWAY_CONF} 2>/dev/null | head -5 || echo "Config file does not exist"')
    run_cmd(ssh, f'cd {PROJECT_DIR} && git remote -v && echo "---" && git log --oneline -3')
    run_cmd(ssh, f'head -30 {PROJECT_DIR}/docker-compose.prod.yml 2>/dev/null')
    run_cmd(ssh, 'df -h /')
    
    ssh.close()
    print("\n[STEP 1 COMPLETE]")


def step2_pull():
    """Step 2: Pull code from Codeup."""
    print("=" * 60)
    print("STEP 2: PULL CODE FROM CODEUP")
    print("=" * 60)
    ssh = get_ssh()
    
    git_url = 'https://kun-an:pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git'
    
    run_cmd(ssh, f'cd {PROJECT_DIR} && git remote set-url origin {git_url}')
    run_cmd(ssh, f'cd {PROJECT_DIR} && git remote -v')
    
    out, err, code = run_cmd(ssh, f'cd {PROJECT_DIR} && git fetch origin master 2>&1', timeout=180)
    if code != 0:
        print("[WARN] Fetch failed, retrying...")
        out, err, code = run_cmd(ssh, f'cd {PROJECT_DIR} && git fetch origin master 2>&1', timeout=180)
    
    if code == 0:
        run_cmd(ssh, f'cd {PROJECT_DIR} && git reset --hard origin/master')
        run_cmd(ssh, f'cd {PROJECT_DIR} && git log --oneline -5')
    else:
        print("[ERROR] Cannot fetch from Codeup!")
    
    ssh.close()
    print("\n[STEP 2 COMPLETE]")


def step3_build():
    """Step 3: Docker compose build and up."""
    print("=" * 60)
    print("STEP 3: DOCKER COMPOSE BUILD & UP")
    print("=" * 60)
    ssh = get_ssh()
    
    # Check current compose file
    print("\n--- Verifying docker-compose.prod.yml ---")
    run_cmd(ssh, f'cat {PROJECT_DIR}/docker-compose.prod.yml')
    
    # Login to ACR
    print("\n--- Logging into ACR ---")
    run_cmd(ssh, 'docker login crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com -u ankun888 -p xiaobai888')
    
    # Stop old containers if any
    print("\n--- Stopping old containers ---")
    run_cmd(ssh, f'cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml down --remove-orphans 2>&1 || echo "No containers to stop"')
    
    # Build and start
    print("\n--- Building and starting containers ---")
    run_cmd(ssh, f'cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache 2>&1', timeout=1800)
    
    print("\n--- Starting containers ---")
    run_cmd(ssh, f'cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d 2>&1', timeout=300)
    
    # Wait for health checks
    print("\n--- Waiting for containers to be healthy (60s) ---")
    time.sleep(60)
    
    # Check status
    print("\n--- Container status ---")
    run_cmd(ssh, 'docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep -E "NAMES|6b099ed3" || echo "No containers"')
    
    ssh.close()
    print("\n[STEP 3 COMPLETE]")


def step4_gateway():
    """Step 4: Deploy gateway configuration."""
    print("=" * 60)
    print("STEP 4: DEPLOY GATEWAY CONFIGURATION")
    print("=" * 60)
    ssh = get_ssh()
    
    # Read the new gateway-routes.conf content from local
    print("\n--- Reading local gateway-routes.conf ---")
    with open('../gateway-routes.conf', 'r', encoding='utf-8') as f:
        new_conf = f.read()
    print(f"Read {len(new_conf)} bytes")
    
    # First, get the full nginx.conf to understand structure
    print("\n--- Fetching full nginx.conf ---")
    out, err, code = run_cmd(ssh, f'docker exec {GATEWAY_CONTAINER} cat /etc/nginx/nginx.conf')
    nginx_conf = out
    
    # Check if include conf.d/*.conf is inside a server block (old structure)
    # We need to add include at http level for server blocks
    need_http_include = 'include /etc/nginx/conf.d/server-*.conf;' not in nginx_conf
    
    if need_http_include:
        print("\n--- Modifying nginx.conf: adding http-level include for server blocks ---")
        # Backup nginx.conf
        run_cmd(ssh, f'docker exec {GATEWAY_CONTAINER} cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak.{int(time.time())}')
        
        # Add include line before the closing } of http block
        # Strategy: add include before the last } (closing http block)
        # More reliably, add it after 'client_max_body_size' line
        add_line = '    include /etc/nginx/conf.d/server-*.conf;'
        
        if 'include /etc/nginx/conf.d/server-*.conf;' not in nginx_conf:
            # Insert after client_max_body_size line
            cmd_insert = (
                f"docker exec {GATEWAY_CONTAINER} sh -c \""
                f"sed -i '/client_max_body_size 100m;/a\\\\    include /etc/nginx/conf.d/server-*.conf;' "
                f"/etc/nginx/nginx.conf\""
            )
            run_cmd(ssh, cmd_insert)
    
    # Backup old config
    print("\n--- Backing up old gateway config ---")
    run_cmd(ssh, f'cp {GATEWAY_CONF} {GATEWAY_CONF}.bak.{int(time.time())} 2>/dev/null || echo "No old config to backup"')
    
    # Deploy new config as server-{DEPLOY_ID}.conf (for http-level include)
    new_conf_path = f'/home/ubuntu/gateway/conf.d/server-{DEPLOY_ID}.conf'
    print(f"\n--- Deploying new config to {new_conf_path} ---")
    
    # Write via Python on remote
    conf_escaped = new_conf.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$')
    write_cmd = f'cat > {new_conf_path} << "NginxConfEOF"\n{new_conf}\nNginxConfEOF'
    run_cmd(ssh, write_cmd, timeout=30)
    
    # Verify new config
    print("\n--- Verifying new config ---")
    run_cmd(ssh, f'cat {new_conf_path}')
    
    # Disable old location-based config
    print("\n--- Disabling old location-based config ---")
    run_cmd(ssh, f'mv {GATEWAY_CONF} {GATEWAY_CONF}.disabled 2>/dev/null || echo "No old config to disable"')
    
    # Copy new config into gateway container
    print("\n--- Copying config into gateway container ---")
    container_conf_path = f'/etc/nginx/conf.d/server-{DEPLOY_ID}.conf'
    run_cmd(ssh, f'docker cp {new_conf_path} {GATEWAY_CONTAINER}:{container_conf_path}')
    
    # Also copy the old config as disabled into container
    run_cmd(ssh, f'docker exec {GATEWAY_CONTAINER} sh -c "[ -f /etc/nginx/conf.d/{DEPLOY_ID}.conf ] && mv /etc/nginx/conf.d/{DEPLOY_ID}.conf /etc/nginx/conf.d/{DEPLOY_ID}.conf.disabled || echo No old config in container"')
    
    # Test nginx config
    print("\n--- Testing nginx configuration ---")
    run_cmd(ssh, f'docker exec {GATEWAY_CONTAINER} nginx -t')
    
    # Reload nginx
    print("\n--- Reloading nginx ---")
    run_cmd(ssh, f'docker exec {GATEWAY_CONTAINER} nginx -s reload')
    
    ssh.close()
    print("\n[STEP 4 COMPLETE]")


def step5_verify():
    """Step 5: Verify deployment."""
    print("=" * 60)
    print("STEP 5: VERIFY DEPLOYMENT")
    print("=" * 60)
    ssh = get_ssh()
    
    # Container status
    print("\n--- Container status ---")
    run_cmd(ssh, 'docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep -E "NAMES|6b099ed3"')
    
    # Test HTTPS access
    print("\n--- Testing HTTPS access ---")
    run_cmd(ssh, f'curl -sk -o /dev/null -w "%{{http_code}}" https://{DOMAIN}/api/health 2>/dev/null || echo "CURL_FAILED"')
    run_cmd(ssh, f'curl -sk -o /dev/null -w "%{{http_code}}" https://{DOMAIN}/ 2>/dev/null || echo "CURL_FAILED"')
    run_cmd(ssh, f'curl -sk -o /dev/null -w "%{{http_code}}" https://{DOMAIN}/admin/ 2>/dev/null || echo "CURL_FAILED"')
    
    # Backend logs
    print("\n--- Backend logs (last 10 lines) ---")
    run_cmd(ssh, f'docker logs --tail 10 {DEPLOY_ID}-backend 2>/dev/null || echo "No backend container"')
    
    ssh.close()
    print("\n[STEP 5 COMPLETE]")


def step6_cleanup():
    """Step 6: Clean up old services/configs."""
    print("=" * 60)
    print("STEP 6: CLEANUP OLD SERVICES")
    print("=" * 60)
    ssh = get_ssh()
    
    # List old disabled configs
    print("\n--- Disabled/old configs ---")
    run_cmd(ssh, f'ls -la /home/ubuntu/gateway/conf.d/*{DEPLOY_ID}* 2>/dev/null || echo "No matching files"')
    
    # Check for orphan containers
    print("\n--- Orphan containers ---")
    run_cmd(ssh, 'docker ps -a --filter "status=exited" --format "table {{.Names}}\t{{.Status}}" | grep -E "NAMES|6b099ed3" || echo "No exited containers"')
    
    ssh.close()
    print("\n[STEP 6 COMPLETE]")





def check_compose():
    """Quick check of server docker-compose files."""
    ssh = get_ssh()
    run_cmd(ssh, f'cat {PROJECT_DIR}/docker-compose.prod.yml')
    run_cmd(ssh, f'cat {PROJECT_DIR}/gateway-routes.conf')
    ssh.close()



def deploy_gateway():
    """Deploy gateway config: modify nginx.conf, deploy new server block, disable old.
    
    Strategy: Use .server extension to avoid being matched by existing 
    include /etc/nginx/conf.d/*.conf (which is inside server blocks).
    Add include /etc/nginx/conf.d/*.server at http level.
    """
    import time as time_module
    import os
    import base64
    
    ssh = get_ssh()
    
    DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
    GATEWAY_CONF_PATH = f'/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf'
    SERVER_CONF_PATH = f'/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server'
    CONTAINER = 'gateway-nginx'
    ts = int(time_module.time())
    
    # 1. Get full nginx.conf
    print("--- 1. Get nginx.conf ---")
    out, err, code = run_cmd(ssh, f'docker exec {CONTAINER} cat /etc/nginx/nginx.conf')
    nginx_conf = out
    
    # 2. Check if http-level include exists
    has_http_include = 'include /etc/nginx/conf.d/*.server;' in nginx_conf
    
    if not has_http_include:
        print("--- 2. Adding http-level include for server blocks ---")
        # Backup nginx.conf
        run_cmd(ssh, f'docker exec {CONTAINER} cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak.{ts}')
        
        # Use python inside container to modify nginx.conf (more reliable than sed)
        python_script = (
            "import re; "
            "conf = open('/etc/nginx/nginx.conf').read(); "
            "new_line = '    include /etc/nginx/conf.d/*.server;\\n'; "
            "# Insert before the last } (closing http block)"
            "idx = conf.rfind('}'); "
            "conf = conf[:idx] + new_line + conf[idx:]; "
            "open('/etc/nginx/nginx.conf', 'w').write(conf); "
            "print('nginx.conf updated successfully')"
        )
        run_cmd(ssh, f"docker exec {CONTAINER} python3 -c '{python_script}'")
        
        # Verify
        print("--- Verify nginx.conf tail ---")
        run_cmd(ssh, f'docker exec {CONTAINER} tail -10 /etc/nginx/nginx.conf')
    else:
        print("--- 2. HTTP-level include already exists ---")
    
    # 3. Read local gateway-routes.conf
    print("--- 3. Reading local gateway-routes.conf ---")
    local_conf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'gateway-routes.conf')
    with open(local_conf_path, 'r', encoding='utf-8') as f:
        new_conf = f.read()
    print(f"Read {len(new_conf)} bytes from {local_conf_path}")
    
    # 4. Write new config to server using .server extension
    print(f"--- 4. Deploying to {SERVER_CONF_PATH} ---")
    conf_b64 = base64.b64encode(new_conf.encode('utf-8')).decode('utf-8')
    run_cmd(ssh, f'echo {conf_b64} | base64 -d > {SERVER_CONF_PATH}')
    
    # 5. Verify
    print("--- 5. Verify new config ---")
    run_cmd(ssh, f'head -10 {SERVER_CONF_PATH}')
    
    # 6. Disable old location-based config
    print("--- 6. Disabling old config ---")
    run_cmd(ssh, f'[ -f {GATEWAY_CONF_PATH} ] && mv {GATEWAY_CONF_PATH} {GATEWAY_CONF_PATH}.disabled.{ts} || echo "No old config"')
    # Also disable in container if present
    run_cmd(ssh, f'docker exec {CONTAINER} sh -c "[ -f /etc/nginx/conf.d/{DEPLOY_ID}.conf ] && mv /etc/nginx/conf.d/{DEPLOY_ID}.conf /etc/nginx/conf.d/{DEPLOY_ID}.conf.disabled.{ts} || echo No old config in container"')
    
    # 7. Copy new config into container using docker cp
    print("--- 7. Copying new config to container ---")
    container_target = f'/etc/nginx/conf.d/{DEPLOY_ID}.server'
    # docker cp may fail if volume is read-only. Try directly via cat/tee from host
    run_cmd(ssh, f'cat {SERVER_CONF_PATH} | docker exec -i {CONTAINER} tee {container_target} > /dev/null')
    
    # 8. Test nginx config
    print("--- 8. Testing nginx config ---")
    out, err, code = run_cmd(ssh, f'docker exec {CONTAINER} nginx -t')
    
    if code != 0:
        print("\n[ERROR] nginx -t failed! Rolling back nginx.conf...")
        # Restore from backup
        run_cmd(ssh, f'docker exec {CONTAINER} cp /etc/nginx/nginx.conf.bak.{ts} /etc/nginx/nginx.conf')
        run_cmd(ssh, f'docker exec {CONTAINER} nginx -t')
        ssh.close()
        return
    
    # 9. Reload
    print("--- 9. Reloading nginx ---")
    run_cmd(ssh, f'docker exec {CONTAINER} nginx -s reload')
    
    ssh.close()
    print("\n[GATEWAY DEPLOYMENT COMPLETE]")



if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'all'
    
    steps = {
        '1': step1_check,
        'check': step1_check,
        '2': step2_pull,
        'pull': step2_pull,
        '3': step3_build,
        'build': step3_build,
        '4': step4_gateway,
        'gateway': step4_gateway,
        '5': step5_verify,
        'verify': step5_verify,
        '6': step6_cleanup,
        'cleanup': step6_cleanup,
        'deploy-gw': deploy_gateway,
    }
    
    if action in steps:
        steps[action]()
    elif action == 'all':
        for step_name in ['check', 'pull', 'build', 'gateway', 'verify', 'cleanup']:
            try:
                steps[step_name]()
            except Exception as e:
                print(f"\n[ERROR in step {step_name}]: {e}")
                import traceback
                traceback.print_exc()
    else:
        print(f"Unknown action: {action}")
        print(f"Available: {list(steps.keys())}")


def verify():
    """Verify deployment."""
    ssh = get_ssh()
    DOMAIN = '6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'
    DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
    
    print("=" * 60)
    print("VERIFY DEPLOYMENT")
    print("=" * 60)
    
    # Container status
    print("\n--- Container Status ---")
    run_cmd(ssh, 'docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "NAMES|6b099ed3"')
    
    # Test HTTPS endpoints
    print("\n--- Testing HTTPS Endpoints ---")
    run_cmd(ssh, f'curl -sk -o /dev/null -w "HTTP %{{http_code}}" https://{DOMAIN}/api/health 2>&1 || echo "CURL_FAILED"')
    run_cmd(ssh, f'curl -sk -o /dev/null -w "HTTP %{{http_code}}" https://{DOMAIN}/ 2>&1 || echo "CURL_FAILED"')
    run_cmd(ssh, f'curl -sk -o /dev/null -w "HTTP %{{http_code}}" https://{DOMAIN}/admin/ 2>&1 || echo "CURL_FAILED"')
    
    # Test health endpoint content
    print("\n--- Health Check Response ---")
    run_cmd(ssh, f'curl -sk https://{DOMAIN}/api/health 2>&1 | head -20')
    
    # Test H5 page
    print("\n--- H5 Homepage (first 500 chars) ---")
    run_cmd(ssh, f'curl -sk https://{DOMAIN}/ 2>&1 | head -20')
    
    # Check gateway config
    print("\n--- Gateway Config Status ---")
    run_cmd(ssh, f'ls -la /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.* 2>&1')
    
    ssh.close()
    print("\n[VERIFY COMPLETE]")

