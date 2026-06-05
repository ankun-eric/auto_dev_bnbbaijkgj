#!/usr/bin/env python3
"""服务器环境预检脚本 - 6项检查"""
import paramiko
import json
import sys

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def ssh_cmd(client, cmd, timeout=30):
    """执行远程命令并返回 stdout"""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out.strip(), err.strip()

def check1_gateway_config(client):
    """预检1: Gateway nginx 配置结构探测"""
    print("=" * 60)
    print("[预检1] Gateway nginx 配置结构探测")
    results = {}
    
    # 检查 gateway 目录
    out, err = ssh_cmd(client, "ls -la /home/ubuntu/gateway/ 2>&1")
    results['gateway_dir'] = out
    
    out, err = ssh_cmd(client, "ls -la /home/ubuntu/gateway/conf.d/ 2>&1")
    results['conf_d'] = out
    
    # 检查 gateway-nginx 容器是否运行
    out, err = ssh_cmd(client, "docker ps --filter name=gateway-nginx --format '{{.Names}} {{.Status}}' 2>&1")
    results['gateway_container'] = out
    
    # 检查已存在的本项目配置
    out, err = ssh_cmd(client, f"ls -la /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf 2>&1")
    results['existing_conf'] = out
    
    # 检查 SSL 证书
    out, err = ssh_cmd(client, "ls -la /home/ubuntu/gateway/ssl/ 2>&1 || ls -la /etc/nginx/ssl/ 2>&1 || echo 'SSL_DIR_NOT_FOUND'")
    results['ssl_certs'] = out
    
    for k, v in results.items():
        print(f"  [{k}]: {v[:200]}")
    return results

def check2_route_conflict(client):
    """预检2: 路由占用检查"""
    print("=" * 60)
    print("[预检2] 路由占用检查")
    results = {}
    
    # 检查是否已有同域名配置
    out, err = ssh_cmd(client, f"grep -r '{DEPLOY_ID}' /home/ubuntu/gateway/conf.d/ 2>&1")
    results['existing_routes'] = out[:300]
    
    # 检查端口占用
    out, err = ssh_cmd(client, "docker ps --format '{{.Names}} {{.Ports}}' 2>&1")
    results['docker_ports'] = out[:500]
    
    # 检查关键端口
    for port in [3001, 8000, 3000]:
        out, err = ssh_cmd(client, f"ss -tlnp | grep :{port} 2>&1 || netstat -tlnp 2>/dev/null | grep :{port}")
        results[f'port_{port}'] = out[:100]
    
    for k, v in results.items():
        print(f"  [{k}]: {v[:200]}")
    return results

def check3_acr_images(client):
    """预检3: ACR 基础镜像版本匹配"""
    print("=" * 60)
    print("[预检3] ACR 基础镜像版本匹配")
    results = {}
    
    # 检查 ACR 登录状态
    out, err = ssh_cmd(client, "docker images --format '{{.Repository}}:{{.Tag}}' | grep crpi-d7zlu3m44f38jufp 2>&1")
    results['acr_images_local'] = out[:500]
    
    # 检查本地缓存的基础镜像
    out, err = ssh_cmd(client, "docker images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | grep 'noob_doker_base' 2>&1")
    results['base_images'] = out[:500]
    
    # 检查 Docker 配置
    out, err = ssh_cmd(client, "cat ~/.docker/config.json 2>&1 | head -20")
    results['docker_config'] = out[:300]
    
    for k, v in results.items():
        print(f"  [{k}]: {v[:200]}")
    return results

def check4_docker_network(client):
    """预检4: Docker 网络拓扑"""
    print("=" * 60)
    print("[预检4] Docker 网络拓扑")
    results = {}
    
    # 列出所有 Docker 网络
    out, err = ssh_cmd(client, "docker network ls 2>&1")
    results['networks'] = out[:500]
    
    # 检查本项目网络
    out, err = ssh_cmd(client, f"docker network inspect {DEPLOY_ID}-network 2>&1 | head -30")
    results['project_network'] = out[:500]
    
    # 检查 gateway 网络
    out, err = ssh_cmd(client, "docker inspect gateway-nginx --format '{{.NetworkSettings.Networks}}' 2>&1")
    results['gateway_network'] = out[:500]
    
    for k, v in results.items():
        print(f"  [{k}]: {v[:200]}")
    return results

def check5_base_image_tools(client):
    """预检5: 基础镜像内置工具检测"""
    print("=" * 60)
    print("[预检5] 基础镜像内置工具检测")
    results = {}
    
    # 检查 python 基础镜像
    out, err = ssh_cmd(client, "docker run --rm crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/python:3.12-slim python3 --version 2>&1")
    results['python_image'] = out[:200]
    
    # 检查 node 基础镜像
    out, err = ssh_cmd(client, "docker run --rm crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/node:20-alpine node --version 2>&1")
    results['node_image'] = out[:200]
    
    for k, v in results.items():
        print(f"  [{k}]: {v[:200]}")
    return results

def check6_disk_space(client):
    """预检6: 磁盘空间检查"""
    print("=" * 60)
    print("[预检6] 磁盘空间检查")
    results = {}
    
    out, err = ssh_cmd(client, "df -h / 2>&1")
    results['disk_root'] = out
    
    out, err = ssh_cmd(client, "df -h /home 2>&1")
    results['disk_home'] = out
    
    out, err = ssh_cmd(client, "du -sh /home/ubuntu/ 2>&1 | head -5")
    results['home_usage'] = out[:200]
    
    out, err = ssh_cmd(client, "docker system df 2>&1")
    results['docker_disk'] = out[:500]
    
    for k, v in results.items():
        print(f"  [{k}]: {v[:200]}")
    return results


def main():
    print(f"开始服务器环境预检 - {DEPLOY_ID}")
    print(f"连接 {USER}@{HOST}:{PORT}")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
        print("SSH 连接成功!\n")
        
        all_results = {}
        
        # 执行6项检查
        all_results['check1_gateway'] = check1_gateway_config(client)
        all_results['check2_routes'] = check2_route_conflict(client)
        all_results['check3_acr'] = check3_acr_images(client)
        all_results['check4_network'] = check4_docker_network(client)
        all_results['check5_tools'] = check5_base_image_tools(client)
        all_results['check6_disk'] = check6_disk_space(client)
        
        # 汇总
        print("\n" + "=" * 60)
        print("预检完成 - 汇总")
        print("=" * 60)
        
        # 保存结果
        with open("C:\\auto_output\\bnbbaijkgj\\precheck_result.txt", "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
        
        print("结果已保存到 precheck_result.txt")
        
    except Exception as e:
        print(f"SSH 连接失败: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    main()
