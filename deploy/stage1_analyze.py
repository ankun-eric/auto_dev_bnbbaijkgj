#!/usr/bin/env python3
"""阶段1：测试环境项目分析 - 修正版"""

import paramiko

TEST_HOST = 'newbb.test.bangbangvip.com'
TEST_PORT = 22
TEST_USER = 'ubuntu'
TEST_PASS = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

def run_ssh(cmd, timeout=60):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=TEST_HOST, port=TEST_PORT, username=TEST_USER, 
                      password=TEST_PASS, timeout=20, allow_agent=False, look_for_keys=False)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return out, err
    finally:
        client.close()

def main():
    print("=" * 60)
    print("测试环境项目分析")
    print("=" * 60)
    
    # 1. 容器状态 - 使用简单的 docker ps
    out, err = run_ssh("docker ps --filter name={} --format '{{.Names}}|{{.Image}}|{{.Status}}'".format(DEPLOY_ID))
    print("\n--- 容器状态 ---")
    print(out)
    if err: print("STDERR:", err)
    
    # 2. 容器详细信息
    out, err = run_ssh("docker ps -a --no-trunc --filter name={} --format '{{.Names}}|{{.Image}}|{{.Ports}}|{{.Status}}'".format(DEPLOY_ID))
    print("\n--- 容器详细信息 ---")
    print(out)
    
    # 3. 镜像列表
    out, err = run_ssh("docker images --format '{{.Repository}}|{{.Tag}}|{{.Size}}' | grep -i '{}'".format(DEPLOY_ID))
    print("\n--- 项目镜像 ---")
    print(out)
    
    # 4. 获取后端镜像详细
    out, err = run_ssh("docker inspect --format '{{.Config.Image}}' {}-backend".format(DEPLOY_ID))
    print("\n--- 后端镜像 ---")
    print(out)
    
    # 5. 获取前端镜像详细
    for name in ['h5', 'admin']:
        out, err = run_ssh("docker inspect --format '{{.Config.Image}}' {}-{}".format(DEPLOY_ID, name))
        print("--- {}镜像: {} ---".format(name, out.strip()))
    
    # 6. docker-compose.prod.yml 内容
    out, err = run_ssh("cat /home/ubuntu/{}/docker-compose.prod.yml".format(DEPLOY_ID))
    print("\n--- docker-compose.prod.yml ---")
    print(out)
    
    # 7. Gateway配置
    out, err = run_ssh("ls -la /home/ubuntu/gateway/conf.d/ | grep '{}'".format(DEPLOY_ID))
    print("\n--- Gateway配置 ---")
    print(out)
    
    # 也检查 .server 后缀
    out, err = run_ssh("cat /home/ubuntu/gateway/conf.d/{}.server 2>/dev/null || echo 'NOT_FOUND'".format(DEPLOY_ID))
    print("\n--- Gateway .server 配置 ---")
    print(out[:3000] if len(out) > 3000 else out)
    
    # 8. 后端Dockerfile FROM指令
    out, err = run_ssh("cat /home/ubuntu/{}/backend/Dockerfile".format(DEPLOY_ID))
    print("\n--- 后端 Dockerfile ---")
    print(out)
    
    # 9. h5 Dockerfile FROM指令
    out, err = run_ssh("cat /home/ubuntu/{}/h5-web/Dockerfile".format(DEPLOY_ID))
    print("\n--- h5-web Dockerfile ---")
    print(out)
    
    # 10. admin Dockerfile FROM指令
    out, err = run_ssh("cat /home/ubuntu/{}/admin-web/Dockerfile".format(DEPLOY_ID))
    print("\n--- admin-web Dockerfile ---")
    print(out)
    
    # 11. nginx配置(主配置)
    out, err = run_ssh("grep -n 'include\|server_name\|listen' /home/ubuntu/gateway/nginx.conf 2>/dev/null | head -30")
    print("\n--- Gateway nginx主配置 ---")
    print(out)
    
    # 12. docker network 信息
    out, err = run_ssh("docker network ls --format '{{.Name}}' | grep '{}'".format(DEPLOY_ID))
    print("\n--- Docker网络 ---")
    print(out)
    
    # 13. 获取所有镜像（包括基础镜像）
    out, err = run_ssh("docker images --format '{{.Repository}}|{{.Tag}}|{{.Size}}' | grep -E 'python|node|nginx|{}' | head -20".format(DEPLOY_ID))
    print("\n--- 相关镜像（含基础） ---")
    print(out)

if __name__ == '__main__':
    main()
