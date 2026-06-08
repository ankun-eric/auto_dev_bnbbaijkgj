#!/usr/bin/env python3
"""生产环境部署脚本：拉取代码 + 重新构建 + 部署验证"""
import paramiko, time, sys

HOST = 'chat.benne-ai.com'
PORT = 22
USER = 'ubuntu'
PASS = 'Benne-ai@#'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJ_DIR = f'/home/ubuntu/{DEPLOY_ID}'

def ssh_connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, PORT, USER, PASS, timeout=20, allow_agent=False, look_for_keys=False)
    return c

def run(c, cmd, timeout=120):
    print(f"  $ {cmd[:100]}...")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    ec = stdout.channel.recv_exit_status()
    if out.strip(): print(f"    out: {out.strip()[:300]}")
    if err.strip(): print(f"    err: {err.strip()[:200]}")
    return out, err, ec

def main():
    c = ssh_connect()
    try:
        print("=" * 60)
        print("开始生产环境部署")
        print("=" * 60)
        
        # Step 1: Git pull from Codeup
        print("\n[步骤1] 从 Codeup 拉取最新代码...")
        out, err, ec = run(c, f"cd {PROJ_DIR} && git fetch codeup master && git reset --hard codeup/master 2>&1")
        if ec != 0:
            # Retry
            print("  重试...")
            out, err, ec = run(c, f"cd {PROJ_DIR} && git pull codeup master 2>&1")
        out, err, ec = run(c, f"cd {PROJ_DIR} && git log --oneline -3")
        print(f"  HEAD: {out.strip()}")
        
        # Step 2: Build and recreate containers
        print("\n[步骤2] 重新构建容器（使用 --no-cache）...")
        out, err, ec = run(c, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1", timeout=600)
        print(f"  Backend build: {'OK' if ec == 0 else 'FAIL'}")
        
        out, err, ec = run(c, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1", timeout=600)
        print(f"  H5-web build: {'OK' if ec == 0 else 'FAIL'}")
        
        out, err, ec = run(c, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache admin-web 2>&1", timeout=600)
        print(f"  Admin-web build: {'OK' if ec == 0 else 'FAIL'}")
        
        # Step 3: Start containers
        print("\n[步骤3] 启动容器...")
        out, err, ec = run(c, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate backend h5-web admin-web 2>&1")
        
        # Step 4: Connect gateway to network
        print("\n[步骤4] Gateway 连接网络...")
        run(c, f"docker network connect {DEPLOY_ID}-network gateway-nginx 2>&1 || echo 'already connected'")
        
        # Step 5: Wait for healthy
        print("\n[步骤5] 等待容器健康检查...")
        for i in range(24):
            time.sleep(10)
            out, err, ec = run(c, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml ps --format '{{{{.Names}}}}|{{{{.Status}}}}' 2>&1")
            lines = [l for l in out.strip().split('\n') if l.strip()]
            healthy = sum(1 for l in lines if 'healthy' in l.lower())
            running = sum(1 for l in lines if 'Up' in l)
            print(f"  [{i+1}/24] running={running} healthy={healthy}")
            if running >= 3 and healthy >= 3:
                print("  所有容器就绪!")
                break
        
        # Step 6: Reload nginx
        print("\n[步骤6] 重载 Nginx...")
        out, err, ec = run(c, "docker exec gateway-nginx nginx -t 2>&1")
        if ec == 0:
            out, err, ec = run(c, "docker exec gateway-nginx nginx -s reload 2>&1")
            print(f"  Nginx reload: {'OK' if ec == 0 else 'FAIL'}")
        else:
            print(f"  Nginx config test FAILED: {out[:200]}")
        
        # Step 7: Verify deployment
        print("\n[步骤7] 验证部署...")
        time.sleep(5)
        
        out, err, ec = run(c, "curl -s -o /dev/null -w '%{http_code}' https://chat.benne-ai.com/api/health 2>&1")
        print(f"  GET /api/health: HTTP {out.strip()}")
        
        out, err, ec = run(c, "curl -s -o /dev/null -w '%{http_code}' https://chat.benne-ai.com/ 2>&1")
        print(f"  GET / (H5): HTTP {out.strip()}")
        
        out, err, ec = run(c, "curl -s -o /dev/null -w '%{http_code}' https://chat.benne-ai.com/admin/ 2>&1")
        print(f"  GET /admin/: HTTP {out.strip()}")
        
        out, err, ec = run(c, "curl -s -o /dev/null -w '%{http_code}' https://chat.benne-ai.com/api/docs 2>&1")
        print(f"  GET /api/docs: HTTP {out.strip()}")
        
        # Step 8: Container status
        print("\n[步骤8] 容器状态:")
        out, err, ec = run(c, f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml ps 2>&1")
        print(out)
        
        print("\n" + "=" * 60)
        print("部署完成!")
        print("=" * 60)
    finally:
        c.close()

if __name__ == '__main__':
    main()
