#!/usr/bin/env python3
"""自动化部署脚本 – brain_game 模块增量部署"""

import paramiko
import sys
import time
import json

# 部署参数
SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASSWORD = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DOMAIN = f"{DEPLOY_ID}.noob-ai.test.bangbangvip.com"
GATEWAY_CONTAINER = "gateway-nginx"
ACR_ADDR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_USER = "ankun888"
ACR_PASSWORD = "xiaobai888"


def ssh_exec(ssh_client, command, timeout=120, description=""):
    """执行 SSH 命令并返回 stdout/stderr/exit_code"""
    if description:
        print(f"\n{'='*60}")
        print(f">>> {description}")
        print(f">>> CMD: {command[:200]}")
        print(f"{'='*60}")
    
    stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    
    if out:
        print(out[:3000])
    if err:
        print(f"[STDERR]: {err[:2000]}")
    print(f"[EXIT_CODE]: {exit_code}")
    return out, err, exit_code


def main():
    print(f"开始部署: {DEPLOY_ID}")
    print(f"服务器: {SSH_HOST}:{SSH_PORT}")
    print(f"域名: {DOMAIN}")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 连接 SSH
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("\n>>> 正在连接 SSH...")
        ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASSWORD, timeout=30)
        print("SSH 连接成功!")
    except Exception as e:
        print(f"SSH 连接失败: {e}")
        return {"status": "失败", "reason": f"SSH连接失败: {e}"}
    
    results = {}
    
    # ==================== 步骤1: Git Pull ====================
    try:
        # 先检查项目目录是否存在
        out, err, ec = ssh_exec(
            ssh,
            f"ls -la {PROJECT_DIR}/.git 2>&1 | head -5",
            description="检查项目目录"
        )
        
        if ec != 0:
            print("项目目录不存在或不是 git 仓库，尝试 clone...")
            out, err, ec = ssh_exec(
                ssh,
                f"cd /home/ubuntu && git clone https://codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git {DEPLOY_ID}",
                timeout=120,
                description="Git Clone 项目"
            )
        else:
            # Git fetch 和 reset
            cmd = f"""
cd {PROJECT_DIR}
git remote remove codeup 2>/dev/null || true
git remote add codeup https://kun-an:pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git
git fetch codeup master 2>&1
git reset --hard codeup/master 2>&1
echo "---GIT LOG---"
git log -3 --oneline
echo "---GIT LOG END---"
"""
            out, err, ec = ssh_exec(ssh, cmd, timeout=120, description="Git Fetch + Reset")
        
        results["git_pull"] = {"exit_code": ec, "output": out[:1000]}
        
        # 获取最新 commit
        out, err, ec = ssh_exec(ssh, f"cd {PROJECT_DIR} && git log -1 --format='%H'", description="获取最新 commit hash")
        build_commit = out.strip()
        results["build_commit"] = build_commit
        print(f"BUILD_COMMIT: {build_commit}")
        
    except Exception as e:
        results["git_pull"] = {"error": str(e)}
        print(f"Git pull 失败: {e}")
    
    # ==================== 步骤2: 构建并启动容器 ====================
    try:
        # 登录 ACR
        cmd = f"""
docker login --username={ACR_USER} --password='{ACR_PASSWORD}' {ACR_ADDR} 2>&1
"""
        out, err, ec = ssh_exec(ssh, cmd, description="Docker 登录 ACR")
        results["docker_login"] = {"exit_code": ec}
        
        # 获取 BUILD_COMMIT
        out, err, ec = ssh_exec(ssh, f"cd {PROJECT_DIR} && git log -1 --format='%H'", description="获取 BUILD_COMMIT")
        build_commit = out.strip()
        
        # 停止旧容器
        cmd = f"""
cd {PROJECT_DIR}
docker compose -f docker-compose.prod.yml down 2>&1
"""
        out, err, ec = ssh_exec(ssh, cmd, timeout=120, description="停止旧容器")
        results["docker_down"] = {"exit_code": ec}
        
        # 构建
        cmd = f"""
cd {PROJECT_DIR}
export BUILD_COMMIT={build_commit}
docker compose -f docker-compose.prod.yml build --pull 2>&1
"""
        out, err, ec = ssh_exec(ssh, cmd, timeout=600, description="Docker Compose Build (--pull)")
        
        if ec != 0:
            print("首次构建失败，尝试不带 --pull 重新构建...")
            out2, err2, ec2 = ssh_exec(
                ssh,
                f"cd {PROJECT_DIR} && export BUILD_COMMIT={build_commit} && docker compose -f docker-compose.prod.yml build 2>&1",
                timeout=600,
                description="Docker Compose Build (no --pull)"
            )
            out = out2
            err = err2
            ec = ec2
        
        results["docker_build"] = {"exit_code": ec, "output_tail": out[-2000:] if len(out) > 2000 else out}
        
        if ec != 0:
            print(f"构建失败！错误: {err[:1000]}")
        else:
            # 启动容器
            cmd = f"""
cd {PROJECT_DIR}
export BUILD_COMMIT={build_commit}
docker compose -f docker-compose.prod.yml up -d 2>&1
"""
            out, err, ec = ssh_exec(ssh, cmd, timeout=120, description="启动容器")
            results["docker_up"] = {"exit_code": ec}
            
            # 等待健康检查
            print("等待容器启动 (15s)...")
            time.sleep(15)
            
            # 查看容器状态
            out, err, ec = ssh_exec(
                ssh,
                f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps 2>&1",
                description="容器状态"
            )
            results["docker_ps"] = out[:2000]
            
            # 加入 gateway 网络
            out, err, ec = ssh_exec(
                ssh,
                f"docker network connect {DEPLOY_ID}-network {GATEWAY_CONTAINER} 2>&1 || echo 'Network already connected or not found'",
                description="连接 Gateway 网络"
            )
            results["network_connect"] = out[:500]
            
    except Exception as e:
        results["docker_build"] = {"error": str(e)}
        print(f"构建过程异常: {e}")
    
    # ==================== 步骤3: 验证 brain_game 接口 ====================
    try:
        print("\n等待后端完全启动 (10s)...")
        time.sleep(10)
        
        # 验证页面
        cmd = f"curl -sI https://{DOMAIN}/brain-game 2>&1 | head -10"
        out, err, ec = ssh_exec(ssh, cmd, description="验证 brain-game 页面 HTTP 头")
        results["brain_game_page"] = out[:1000]
        
        # 验证 API - 地区列表
        cmd = f"curl -s https://{DOMAIN}/api/brain-game/regions 2>&1 | head -500"
        out, err, ec = ssh_exec(ssh, cmd, description="验证 /api/brain-game/regions")
        results["brain_game_regions"] = out[:2000]
        
        # 验证地区树
        cmd = f"curl -s https://{DOMAIN}/api/brain-game/regions/tree 2>&1 | head -500"
        out, err, ec = ssh_exec(ssh, cmd, description="验证 /api/brain-game/regions/tree")
        results["brain_game_tree"] = out[:2000]
        
        # 手动触发种子同步
        cmd = f"curl -s -X POST https://{DOMAIN}/api/brain-game/regions/sync-seed 2>&1"
        out, err, ec = ssh_exec(ssh, cmd, description="手动触发种子数据同步")
        results["sync_seed"] = out[:1000]
        
    except Exception as e:
        results["api_verify"] = {"error": str(e)}
        print(f"API 验证异常: {e}")
    
    # ==================== 步骤4: 查看后端日志 ====================
    try:
        out, err, ec = ssh_exec(
            ssh,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml logs backend --tail=100 2>&1 | grep -i 'brain_game\\|region\\|seed' || echo 'No brain_game related logs found'",
            description="后端日志 (brain_game 相关)"
        )
        results["backend_logs"] = out[:2000]
        
        # 也查看更广泛的日志
        out, err, ec = ssh_exec(
            ssh,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml logs backend --tail=50 2>&1",
            description="后端日志 (最近 50 行)"
        )
        results["backend_logs_full"] = out[:2000]
        
    except Exception as e:
        results["logs"] = {"error": str(e)}
    
    # ==================== 额外验证：尝试直接 curl backend 容器 ====================
    try:
        out, err, ec = ssh_exec(
            ssh,
            f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml exec -T backend curl -s http://localhost:8000/api/brain-game/regions 2>&1 | head -200",
            description="直接验证 backend 容器内部 API"
        )
        results["backend_internal"] = out[:2000]
    except Exception as e:
        results["backend_internal"] = f"Error: {e}"
    
    ssh.close()
    
    # 汇总输出
    print("\n\n" + "="*60)
    print("部署结果汇总")
    print("="*60)
    for key, val in results.items():
        print(f"\n[{key}]:")
        if isinstance(val, dict):
            print(json.dumps(val, ensure_ascii=False, indent=2)[:1000])
        else:
            print(str(val)[:1000])
    
    return {"status": "completed", "results": results}


if __name__ == "__main__":
    result = main()
    print("\n\nFINAL_RESULT:", json.dumps(result, ensure_ascii=False, indent=2)[:5000])
