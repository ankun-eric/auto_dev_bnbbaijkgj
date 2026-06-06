#!/usr/bin/env python3
"""验证 brain_game API 和种子数据"""

import paramiko
import sys

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASSWORD = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
DOMAIN = "6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"


def ssh_exec(ssh_client, command, timeout=30):
    stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    ec = stdout.channel.recv_exit_status()
    return out, err, ec


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print("连接 SSH...")
    ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASSWORD, timeout=30)
    print("SSH 连接成功!")
    
    # Test 1: Regions API
    print("\n" + "="*60)
    print("1. 验证 /api/brain-game/regions")
    out, err, ec = ssh_exec(ssh, f"curl -s https://{DOMAIN}/api/brain-game/regions")
    print(f"Exit: {ec}")
    print(f"Response: {out[:3000]}")
    if err:
        print(f"Stderr: {err[:500]}")
    
    # 解析 HTTP 状态码
    out2, err2, ec2 = ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/brain-game/regions")
    print(f"HTTP Status: {out2.strip()}")
    
    # Test 2: Regions Tree API
    print("\n" + "="*60)
    print("2. 验证 /api/brain-game/regions/tree")
    out, err, ec = ssh_exec(ssh, f"curl -s https://{DOMAIN}/api/brain-game/regions/tree")
    print(f"Exit: {ec}")
    print(f"Response: {out[:3000]}")
    
    out2, err2, ec2 = ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/brain-game/regions/tree")
    print(f"HTTP Status: {out2.strip()}")
    
    # Test 3: brain-game page
    print("\n" + "="*60)
    print("3. 验证 /brain-game 页面")
    out, err, ec = ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/brain-game")
    print(f"HTTP Status: {out.strip()}")
    
    out, err, ec = ssh_exec(ssh, f"curl -s -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/brain-game/")
    print(f"HTTP Status (with slash): {out.strip()}")
    
    # Test 4: 容器状态
    print("\n" + "="*60)
    print("4. 容器运行状态")
    out, err, ec = ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml ps --format json")
    print(f"Containers: {out[:2000]}")
    
    # Test 5: 后端日志查找 brain_game
    print("\n" + "="*60)
    print("5. 后端日志中 brain_game 相关内容")
    out, err, ec = ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml logs backend --tail=200 2>&1")
    
    found_lines = []
    for line in out.split('\n'):
        lower = line.lower()
        if any(kw in lower for kw in ['brain_game', 'region', 'sync_seed', 'lifespan', 'brain-game']):
            found_lines.append(line)
    
    if found_lines:
        for line in found_lines:
            print(line[:500])
    else:
        print("未找到 brain_game 相关日志。检查 lifespan 启动日志:")
        for line in out.split('\n'):
            if 'lifespan' in line.lower() or 'startup' in line.lower() or 'started' in line.lower():
                print(line[:500])
    
    # Test 6: 检查数据库中是否有数据
    print("\n" + "="*60)
    print("6. 数据库种子数据验证")
    out, err, ec = ssh_exec(ssh,
        f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml exec -T db mysql -uroot -pbini_health_2026 bini_health -e 'SELECT COUNT(*) as count FROM brain_game_regions;' 2>&1"
    )
    print(f"brain_game_regions 表记录数: {out[:500]}")
    if err:
        print(f"Stderr: {err[:500]}")
    
    ssh.close()
    
    print("\n" + "="*60)
    print("验证完成!")
    print("="*60)


if __name__ == "__main__":
    main()
