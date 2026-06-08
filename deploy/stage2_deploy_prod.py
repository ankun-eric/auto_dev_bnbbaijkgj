#!/usr/bin/env python3
"""阶段2：生产环境部署"""

import paramiko
import time
import os

PROD_HOST = 'chat.benne-ai.com'
PROD_PORT = 22
PROD_USER = 'ubuntu'
PROD_PASS = 'Benne-ai@#'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
ACR_REG = 'crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com'
ACR_USER = 'ankun888'
ACR_PASS = 'xiaobai888'

LOCAL_DEPLOY_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR = '/home/ubuntu/{}'.format(DEPLOY_ID)

def run_ssh(cmd, timeout=120):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=PROD_HOST, port=PROD_PORT, username=PROD_USER,
                      password=PROD_PASS, timeout=20, allow_agent=False, look_for_keys=False)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return out, err, stdout.channel.recv_exit_status()
    finally:
        client.close()

def upload_file(local_path, remote_path):
    """Upload a file via SCP"""
    transport = paramiko.Transport((PROD_HOST, PROD_PORT))
    transport.connect(username=PROD_USER, password=PROD_PASS)
    sftp = paramiko.SFTPClient.from_transport(transport)
    try:
        sftp.put(local_path, remote_path)
        print("  已上传: {} -> {}".format(local_path, remote_path))
        return True
    except Exception as e:
        print("  上传失败: {}".format(e))
        return False
    finally:
        sftp.close()
        transport.close()

def main():
    print("=" * 60)
    print("阶段2：生产环境部署")
    print("=" * 60)

    # Step 1: ACR 登录
    print("\n[步骤1] ACR 登录")
    out, err, ec = run_ssh("docker login --username={} --password={} {} 2>&1".format(ACR_USER, ACR_PASS, ACR_REG))
    if ec == 0:
        print("  ACR 登录成功")
    else:
        print("  ACR 登录失败: {} {}".format(out, err))
        return

    # Step 2: 停止旧容器
    print("\n[步骤2] 停止旧容器")
    out, err, ec = run_ssh("cd {} && docker compose -f docker-compose.prod.yml down 2>&1".format(PROJ_DIR))
    print("  结果: {}".format(out.strip()[:200] if out.strip() else '完成'))
    
    # Also force remove any remaining project containers
    run_ssh("docker ps -a --filter name={}- --format {{{{.Names}}}} | xargs -r docker rm -f 2>&1".format(DEPLOY_ID))

    # Step 3: 上传适配后的配置文件
    print("\n[步骤3] 上传配置文件")
    upload_file(
        os.path.join(LOCAL_DEPLOY_DIR, 'docker-compose.prod.yml'),
        '{}/docker-compose.prod.yml'.format(PROJ_DIR)
    )
    upload_file(
        os.path.join(LOCAL_DEPLOY_DIR, 'gateway-routes.conf'),
        '{}/gateway-routes.conf'.format(PROJ_DIR)
    )

    # Step 4: 创建 .env 文件
    print("\n[步骤4] 创建 .env 文件")
    build_commit = "publish-{}".format(time.strftime('%Y%m%d%H%M%S'))
    out, err, ec = run_ssh("echo 'BUILD_COMMIT={}' > {}/.env".format(build_commit, PROJ_DIR))
    print("  BUILD_COMMIT={}".format(build_commit))

    # Step 5: 从 ACR 拉取镜像（确保使用 ACR 而非 Docker Hub）
    print("\n[步骤5] 从 ACR 拉取镜像")
    
    images = [
        "{}/noob_ai_apps/{}-backend:latest".format(ACR_REG, DEPLOY_ID),
        "{}/noob_ai_apps/{}-h5-web:latest".format(ACR_REG, DEPLOY_ID),
        "{}/noob_ai_apps/{}-admin-web:latest".format(ACR_REG, DEPLOY_ID),
    ]
    
    for img in images:
        print("  拉取: {}".format(img))
        out, err, ec = run_ssh("docker pull {} 2>&1".format(img))
        if ec == 0:
            print("    ✅ OK")
        else:
            print("    ❌ 失败: {}".format(err[-200:] if err else out[-200:]))
    
    # Step 6: 启动新容器
    print("\n[步骤6] 启动新容器")
    out, err, ec = run_ssh("cd {} && docker compose -f docker-compose.prod.yml up -d 2>&1".format(PROJ_DIR))
    print("  结果: {}".format(out.strip()[:300] if out.strip() else '完成'))
    
    if ec != 0:
        print("  ❌ 启动失败!")
        print(err)
        return

    # Step 7: 等待健康检查
    print("\n[步骤7] 等待健康检查...")
    max_wait = 30  # 30 * 5 = 150 seconds
    for i in range(max_wait):
        time.sleep(5)
        out, err, ec = run_ssh("cd {} && docker compose -f docker-compose.prod.yml ps --format '{{{{.Names}}}}|{{{{.Status}}}}' 2>&1".format(PROJ_DIR))
        lines = [l for l in out.strip().split('\n') if l.strip()]
        healthy = sum(1 for l in lines if 'healthy' in l.lower())
        total = len(lines)
        print("  [{}/{}] {}/{} 容器健康".format(i+1, max_wait, healthy, total))
        if total > 0 and healthy == total:
            print("  ✅ 所有容器健康检查通过!")
            break
    else:
        print("  ⚠️ 等待超时，查看状态...")
        out, err, ec = run_ssh("cd {} && docker compose -f docker-compose.prod.yml ps 2>&1".format(PROJ_DIR))
        print(out)
        out, err, ec = run_ssh("cd {} && docker compose -f docker-compose.prod.yml logs --tail=30 2>&1".format(PROJ_DIR))
        print(out[-2000:])

    # Step 8: 更新 gateway 配置
    print("\n[步骤8] 更新 gateway 配置")
    
    # 备份旧配置
    out, err, ec = run_ssh("mkdir -p /home/ubuntu/gateway/conf.d.bak/ && cp /home/ubuntu/gateway/conf.d/{}.conf /home/ubuntu/gateway/conf.d.bak/{}.conf.bak.{} 2>&1 || echo 'no old config'".format(DEPLOY_ID, DEPLOY_ID, time.strftime('%Y%m%d%H%M%S')))
    print("  备份: {}".format(out.strip()[:100]))
    
    # 部署新配置
    out, err, ec = run_ssh("cp {}/gateway-routes.conf /home/ubuntu/gateway/conf.d/{}.conf".format(PROJ_DIR, DEPLOY_ID))
    print("  部署: {}".format("OK" if ec == 0 else "FAIL"))
    
    # 连接 gateway 到项目网络
    run_ssh("docker network connect {}-network gateway-nginx 2>&1 || true".format(DEPLOY_ID))
    
    # 测试语法
    out, err, ec = run_ssh("docker exec gateway-nginx nginx -t 2>&1")
    print("  nginx -t: {}".format(out.strip()[:200]))
    
    if ec == 0:
        # 重载
        out, err, ec = run_ssh("docker exec gateway-nginx nginx -s reload 2>&1")
        print("  reload: {}".format("OK" if ec == 0 else "FAIL"))
    else:
        print("  ❌ nginx 语法错误，请检查配置!")
        return
    
    # Step 9: 验证
    print("\n[步骤9] 验证部署")
    time.sleep(3)
    
    # SSL 验证
    out, err, ec = run_ssh("curl -sI https://chat.benne-ai.com/api/health 2>&1 | head -5")
    print("  /api/health: {}".format(out.strip()[:200]))
    
    out, err, ec = run_ssh("curl -sI https://chat.benne-ai.com/ 2>&1 | head -5")
    print("  / (H5): {}".format(out.strip()[:200]))
    
    out, err, ec = run_ssh("curl -sI https://chat.benne-ai.com/admin/ 2>&1 | head -5")
    print("  /admin/: {}".format(out.strip()[:200]))
    
    # 容器状态
    out, err, ec = run_ssh("cd {} && docker compose -f docker-compose.prod.yml ps 2>&1".format(PROJ_DIR))
    print("\n--- 容器状态 ---")
    print(out)

    print("\n" + "=" * 60)
    print("阶段2 部署完成！")
    print("=" * 60)

if __name__ == '__main__':
    main()
