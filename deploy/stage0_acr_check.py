#!/usr/bin/env python3
"""阶段0.5：ACR连通性验证 + 阶段1：测试环境项目状态分析"""

import paramiko
import sys

TEST_HOST = 'newbb.test.bangbangvip.com'
TEST_PORT = 22
TEST_USER = 'ubuntu'
TEST_PASS = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

ACR_REGISTRY = 'crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com'
ACR_USER = 'ankun888'
ACR_PASS = 'xiaobai888'

def run_ssh(host, port, user, passwd, cmd, timeout=60):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, port=port, username=user, password=passwd, timeout=20, allow_agent=False, look_for_keys=False)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return out, err, stdout.channel.recv_exit_status()
    finally:
        client.close()

def main():
    print("=" * 60)
    print("阶段0.5: ACR连通性验证")
    print("=" * 60)

    # Test ACR login
    cmd = f"docker login --username={ACR_USER} --password={ACR_PASS} {ACR_REGISTRY} 2>&1"
    out, err, exit_code = run_ssh(TEST_HOST, TEST_PORT, TEST_USER, TEST_PASS, cmd)
    print(f"ACR登录结果 (exit={exit_code}):")
    print(out)
    if err:
        print(err)
    acr_ok = exit_code == 0
    print(f"ACR连通性: {'✅ 通过' if acr_ok else '❌ 失败'}")

    print("\n" + "=" * 60)
    print("阶段1.1: 测试环境项目状态分析")
    print("=" * 60)

    cmds = {
        "项目目录检查": f"ls -la /home/ubuntu/{DEPLOY_ID}/ 2>&1 | head -30",
        "项目容器状态": f"docker ps -a --filter 'name={DEPLOY_ID}-' --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' 2>&1",
        "Docker网络": f"docker network ls --filter 'name={DEPLOY_ID}-' --format '{{.Name}}' 2>&1",
        "docker-compose文件": f"ls -la /home/ubuntu/{DEPLOY_ID}/docker-compose.prod.yml 2>&1",
        "Gateway路由配置": f"cat /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf 2>&1 | head -80",
        "项目容器镜像详情": f"docker ps --filter 'name={DEPLOY_ID}-' --format '{{.Names}} {{.Image}}' 2>&1",
        "所有相关镜像": f"docker images --filter 'reference=*{DEPLOY_ID}*' --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' 2>&1",
        "Dockerfile列表": f"find /home/ubuntu/{DEPLOY_ID}/ -name 'Dockerfile' -o -name 'Dockerfile.*' 2>&1 | head -20"
    }

    for title, cmd in cmds.items():
        print(f"\n--- {title} ---")
        out, err, exit_code = run_ssh(TEST_HOST, TEST_PORT, TEST_USER, TEST_PASS, cmd)
        print(out)
        if err:
            print(f"STDERR: {err}")

    # Check .env.production
    print("\n--- .env.production ---")
    cmd = f"cat /home/ubuntu/{DEPLOY_ID}/.env.production 2>&1"
    out, err, _ = run_ssh(TEST_HOST, TEST_PORT, TEST_USER, TEST_PASS, cmd)
    print(out)

if __name__ == '__main__':
    main()
