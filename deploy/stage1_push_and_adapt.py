#!/usr/bin/env python3
"""阶段1：推送镜像到ACR + 拉取和适配配置文件"""

import paramiko
import os

TEST_HOST = 'newbb.test.bangbangvip.com'
TEST_PORT = 22
TEST_USER = 'ubuntu'
TEST_PASS = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
ACR_REG = 'crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com'
ACR_NS = 'noob_ai_apps'
ACR_BASE_NS = 'noob_doker_base'
ACR_USER = 'ankun888'
ACR_PASS = 'xiaobai888'

def run_ssh(cmd, timeout=120):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=TEST_HOST, port=TEST_PORT, username=TEST_USER,
                      password=TEST_PASS, timeout=20, allow_agent=False, look_for_keys=False)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return out, err, stdout.channel.recv_exit_status()
    finally:
        client.close()

def main():
    acr_prefix = "{}/{}/{}".format(ACR_REG, ACR_NS, DEPLOY_ID)
    
    # Step 1: Tag and push project images to ACR
    print("=" * 60)
    print("步骤1: 推送项目镜像到ACR")
    print("=" * 60)
    
    services = {
        'backend': 'backend',
        'h5-web': 'h5-web', 
        'admin-web': 'admin-web'
    }
    
    for svc_name, local_tag in services.items():
        local_img = "{}-{}:latest".format(DEPLOY_ID, local_tag)
        acr_img = "{}-{}:latest".format(acr_prefix, svc_name)
        
        print("\n处理: {} -> {}".format(local_img, acr_img))
        
        # Check if local image exists
        out, err, ec = run_ssh("docker images -q {}".format(local_img))
        if not out.strip():
            print("  警告: 本地镜像 {} 不存在，跳过".format(local_img))
            continue
        
        # Tag
        out, err, ec = run_ssh("docker tag {} {}".format(local_img, acr_img))
        print("  Tag: {}".format("OK" if ec == 0 else "FAIL: " + err))
        
        # Push
        out, err, ec = run_ssh("docker push {}".format(acr_img))
        print("  Push: {}".format("OK" if ec == 0 else "FAIL"))
        if out: print(out[-200:])
        if err: print("  ERR:", err[-200:])
    
    # Step 2: Push mysql:8.0 base image to ACR
    print("\n步骤2: 确保mysql:8.0在ACR基础镜像空间")
    mysql_acr = "{}/{}/mysql:8.0".format(ACR_REG, ACR_BASE_NS)
    out, err, ec = run_ssh("docker manifest inspect {} 2>&1".format(mysql_acr))
    if ec != 0:
        print("  mysql:8.0 不在ACR，拉取并推送...")
        run_ssh("docker pull mysql:8.0")
        run_ssh("docker tag mysql:8.0 {}".format(mysql_acr))
        out, err, ec = run_ssh("docker push {}".format(mysql_acr))
        print("  Push: {}".format("OK" if ec == 0 else "FAIL"))
    else:
        print("  mysql:8.0 已在ACR")
    
    # Step 3: Verify ACR manifests
    print("\n步骤3: 验证ACR镜像")
    for svc_name in ['backend', 'h5-web', 'admin-web']:
        acr_img = "{}-{}:latest".format(acr_prefix, svc_name)
        out, err, ec = run_ssh("docker manifest inspect {} 2>&1 | head -5".format(acr_img))
        print("  {}: {}".format(svc_name, "OK" if ec == 0 else "FAIL: " + err[:100]))
    
    # Step 4: Collect test gateway config for reference
    print("\n步骤4: 拉取gateway配置")
    out, err, ec = run_ssh("cat /home/ubuntu/gateway/conf.d/{}.server".format(DEPLOY_ID))
    if ec == 0:
        print("  测试环境gateway配置已获取")
    
    print("\n阶段1完成！")

if __name__ == '__main__':
    main()
