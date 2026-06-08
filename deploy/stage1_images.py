#!/usr/bin/env python3
"""获取容器镜像信息和生产环境预检"""

import paramiko

TEST_HOST = 'newbb.test.bangbangvip.com'
TEST_PORT = 22
TEST_USER = 'ubuntu'
TEST_PASS = 'Newbang888'
PROD_HOST = 'chat.benne-ai.com'
PROD_PORT = 22
PROD_USER = 'ubuntu'
PROD_PASS = 'Benne-ai@#'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

def run_ssh(host, port, user, passwd, cmd, timeout=60):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, port=port, username=user, password=passwd,
                      timeout=20, allow_agent=False, look_for_keys=False)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return out, err
    finally:
        client.close()

def main():
    # 获取容器信息 - 不用Go template
    print("=" * 60)
    print("测试环境容器信息")
    print("=" * 60)
    
    out, err = run_ssh(TEST_HOST, TEST_PORT, TEST_USER, TEST_PASS, 
                       "docker ps --filter name={}".format(DEPLOY_ID))
    print(out)
    
    # 用 inspect 获取每个容器的镜像
    for svc in ['backend', 'h5', 'admin', 'db']:
        cname = "{}-{}".format(DEPLOY_ID, svc)
        out, err = run_ssh(TEST_HOST, TEST_PORT, TEST_USER, TEST_PASS,
                          "docker inspect --format '{{.Config.Image}}' {} 2>&1".format(cname))
        print("{} image: {}".format(cname, out.strip()))
    
    # docker images 直接输出
    out, err = run_ssh(TEST_HOST, TEST_PORT, TEST_USER, TEST_PASS, "docker images | head -30")
    print("\n--- Docker镜像列表 ---")
    print(out)
    
    # 从docker inspect获取完整镜像信息
    out, err = run_ssh(TEST_HOST, TEST_PORT, TEST_USER, TEST_PASS,
                       "docker inspect --format '{{range .Containers}}{{.Name}} -> {{.Image}}{{\"\\n\"}}{{end}}' 2>&1 | grep '{}'".format(DEPLOY_ID))
    print("\n--- 容器->镜像映射 ---")
    print(out)
    
    # 生产环境预检
    print("\n" + "=" * 60)
    print("生产环境预检 (阶段2.0)")
    print("=" * 60)
    
    # 预检1: Gateway nginx 配置
    out, err = run_ssh(PROD_HOST, PROD_PORT, PROD_USER, PROD_PASS,
                       "cat /home/ubuntu/gateway/nginx.conf 2>&1 | head -20")
    print("\n--- 生产环境 Gateway nginx.conf (前20行) ---")
    print(out)
    
    # 检查是否使用 .server 格式
    out, err = run_ssh(PROD_HOST, PROD_PORT, PROD_USER, PROD_PASS,
                       "grep -n 'include.*server\|include.*conf.d' /home/ubuntu/gateway/nginx.conf 2>&1")
    print("--- Gateway include ---")
    print(out)
    
    # 检查 conf.d 目录
    out, err = run_ssh(PROD_HOST, PROD_PORT, PROD_USER, PROD_PASS,
                       "ls -la /home/ubuntu/gateway/conf.d/ 2>&1")
    print("\n--- 生产环境 conf.d ---")
    print(out)
    
    # 预检2: 路由占用检查
    out, err = run_ssh(PROD_HOST, PROD_PORT, PROD_USER, PROD_PASS,
                       "grep -rn 'location\|server_name' /home/ubuntu/gateway/conf.d/ 2>&1")
    print("\n--- 路由占用 ---")
    print(out)
    
    # 预检3: Docker网络
    out, err = run_ssh(PROD_HOST, PROD_PORT, PROD_USER, PROD_PASS,
                       "docker ps -a --filter name=gateway-nginx 2>&1")
    print("\n--- gateway-nginx容器 ---")
    print(out)
    
    out, err = run_ssh(PROD_HOST, PROD_PORT, PROD_USER, PROD_PASS,
                       "docker network ls --filter name={}-network 2>&1".format(DEPLOY_ID))
    print("--- 项目网络 ---")
    print(out)
    
    # 检查已有项目部署
    out, err = run_ssh(PROD_HOST, PROD_PORT, PROD_USER, PROD_PASS,
                       "ls -la /home/ubuntu/{}/ 2>&1 | head -10".format(DEPLOY_ID))
    print("--- 生产环境项目目录 ---")
    print(out)
    
    # 预检4: 磁盘空间
    out, err = run_ssh(PROD_HOST, PROD_PORT, PROD_USER, PROD_PASS,
                       "df -h / 2>&1")
    print("\n--- 生产环境磁盘 ---")
    print(out)
    
    # 生产环境 SSL证书检查
    out, err = run_ssh(PROD_HOST, PROD_PORT, PROD_USER, PROD_PASS,
                       "ls -la /home/ubuntu/gateway/ssl/ 2>&1")
    print("\n--- 生产环境 SSL证书 ---")
    print(out)

if __name__ == '__main__':
    main()
