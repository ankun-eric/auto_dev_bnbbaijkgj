"""
远程部署脚本：增量更新 h5-web 前端容器
"""
import paramiko
import time
import sys

HOST = '134.175.97.26'
PORT = 22
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_DIR = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
COMPOSE_FILE = 'docker-compose.prod.yml'

def run_cmd(ssh, cmd, timeout=60):
    """执行远程命令并返回输出"""
    print(f'  [CMD] {cmd[:120]}...' if len(cmd) > 120 else f'  [CMD] {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if err:
        print(f'  [STDERR] {err[:500]}')
    return out, err

def main():
    print('=' * 60)
    print('阶段 3：远程增量部署 - h5-web 前端更新')
    print('=' * 60)
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print('\n[1/7] 连接服务器...')
        ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=20, banner_timeout=20)
        print('  连接成功')
        
        # Step 1: 磁盘检查
        print('\n[2/7] 磁盘空间检查...')
        out, _ = run_cmd(ssh, 'df -h / | tail -1', timeout=10)
        print(f'  {out.strip()}')

        # Step 2: Git pull
        print('\n[3/7] Git pull 最新代码...')
        out, err = run_cmd(ssh, f'cd {PROJECT_DIR} && git fetch --depth 1 codeup master 2>&1 && git reset --hard codeup/master 2>&1 && git clean -fd 2>&1', timeout=60)
        print(f'  {out.strip()[:500]}')
        
        # 验证 Git 状态
        out, _ = run_cmd(ssh, f'cd {PROJECT_DIR} && git log -1 --oneline && git status --short 2>&1 | head -5', timeout=15)
        print(f'  Git: {out.strip()[:300]}')
        
        # Step 3: 生成 BUILD_COMMIT
        print('\n[4/7] 生成 BUILD_COMMIT...')
        out, _ = run_cmd(ssh, f'cd {PROJECT_DIR} && BUILD_COMMIT=$(git log -1 --format="%H") && echo "BUILD_COMMIT=$BUILD_COMMIT" && export BUILD_COMMIT', timeout=10)
        build_commit = out.strip().split('=')[-1] if '=' in out else 'unknown'
        print(f'  BUILD_COMMIT={build_commit}')
        
        # Step 4: 登录 ACR
        print('\n[5/7] 登录 ACR...')
        out, err = run_cmd(ssh, 'docker login --username=ankun888 --password=xiaobai888 crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com 2>&1', timeout=30)
        if 'Login Succeeded' in out:
            print('  ACR 登录成功')
        else:
            print(f'  ACR 登录结果: {out.strip()[:200]}')

        # Step 5: 构建 h5-web 容器（仅前端）
        print('\n[6/7] 构建 h5-web 容器...')
        build_cmd = f'cd {PROJECT_DIR} && BUILD_COMMIT={build_commit} docker compose -f {COMPOSE_FILE} build --pull h5-web 2>&1'
        print('  开始构建（可能需要几分钟）...')
        out, err = run_cmd(ssh, build_cmd, timeout=600)
        # 打印最后部分
        lines = out.strip().split('\n')
        for line in lines[-30:]:
            print(f'  {line[:200]}')
        
        if 'ERROR' in out or 'error' in out.lower():
            print('  构建可能有错误，尝试不使用 --pull...')
            build_cmd2 = f'cd {PROJECT_DIR} && BUILD_COMMIT={build_commit} docker compose -f {COMPOSE_FILE} build h5-web 2>&1'
            out2, err2 = run_cmd(ssh, build_cmd2, timeout=600)
            print(f'  重新构建结果: {out2.strip()[-500:]}')
        
        # Step 6: 重启 h5-web
        print('\n[7/7] 重启 h5-web 容器...')
        out, _ = run_cmd(ssh, f'cd {PROJECT_DIR} && docker compose -f {COMPOSE_FILE} up -d h5-web 2>&1', timeout=60)
        print(f'  {out.strip()[:500]}')

        # Step 7: 等待健康检查
        print('\n等待容器健康检查（最多 120 秒）...')
        healthy = False
        for i in range(24):
            time.sleep(5)
            out, _ = run_cmd(ssh, f"docker ps --filter name={DEPLOY_ID}-h5 --format '{{{{.Status}}}}' 2>&1", timeout=10)
            status = out.strip()
            print(f'  [{i+1}/24] h5-web: {status}')
            if 'healthy' in status.lower():
                healthy = True
                break
        
        if healthy:
            print('\n✅ h5-web 容器健康检查通过！')
        else:
            print('\n⚠️ 等待超时，检查容器日志...')
            out, _ = run_cmd(ssh, f'docker logs --tail=30 {DEPLOY_ID}-h5 2>&1', timeout=15)
            print(f'  最近日志:\n{out[:800]}')
        
        # 确保 gateway 加入网络
        print('\n确保 gateway 已加入项目网络...')
        out, _ = run_cmd(ssh, f'docker network connect {DEPLOY_ID}-network gateway-nginx 2>&1 || echo "已连接"', timeout=10)
        print(f'  {out.strip()[:200]}')
        
        # 验证 gateway 配置
        print('\n验证 gateway 配置...')
        out, _ = run_cmd(ssh, 'docker exec gateway-nginx nginx -t 2>&1', timeout=10)
        print(f'  {out.strip()[:300]}')
        
        # SSL 连通性验证
        print('\nSSL 连通性验证...')
        out, _ = run_cmd(ssh, f'curl -sI https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com/ 2>&1 | head -15', timeout=20)
        print(f'  {out.strip()[:500]}')
        
        # 最终状态
        print('\n' + '=' * 60)
        print('部署完成！最终容器状态：')
        out, _ = run_cmd(ssh, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}'", timeout=10)
        print(out)
        
        print(f'\n访问地址: https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com/')
        
    except Exception as e:
        print(f'\n❌ 错误: {e}')
        import traceback
        traceback.print_exc()
    finally:
        ssh.close()
        print('\nSSH 连接已关闭')

if __name__ == '__main__':
    main()
