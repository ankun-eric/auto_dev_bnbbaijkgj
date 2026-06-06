"""Phase 1.5: 服务器环境预检 (6项)"""
import paramiko
import sys

HOST = 'newbb.test.bangbangvip.com'
PORT = 22
USER = 'ubuntu'
PASSWORD = 'Newbang888'

def run_cmd(client, cmd, timeout=30):
    """Run a command and return stdout/stderr."""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=20, banner_timeout=15)
        print("=" * 60)
        print("阶段 1.5：服务器环境预检")
        print("=" * 60)
        
        # 1. Gateway 结构
        print("\n[1/6] Gateway 容器状态")
        out, err = run_cmd(client, 'docker ps --filter name=gateway-nginx --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"')
        print(out or '(空)')
        if err:
            print(f"  [WARN] {err[:200]}")
        
        # 1b. Gateway conf.d
        print("\n[1b] Gateway conf.d 目录")
        out, err = run_cmd(client, 'ls -la /home/ubuntu/gateway/conf.d/ 2>/dev/null || echo "目录不存在"')
        print(out[:500] or '(空)')
        
        # 2. 路由占用检查
        print("\n[2/6] 路由占用检查")
        out, err = run_cmd(client, 'ls /home/ubuntu/gateway/conf.d/6b099ed3*.conf 2>/dev/null && echo "已存在" || echo "未占用"')
        print(out.strip())
        
        # 3. Docker 网络
        print("\n[3/6] Docker 网络")
        out, err = run_cmd(client, 'docker network ls --filter name=6b099ed3')
        print(out or '(无)')
        
        # 4. ACR 镜像拉取测试
        print("\n[4/6] ACR 基础镜像拉取测试")
        out, err = run_cmd(client, 'docker pull crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/python:3.12-slim 2>&1 | tail -3', timeout=60)
        print(out[:300])
        
        # 5. Docker 工具版本
        print("\n[5/6] Docker 工具版本")
        out, err = run_cmd(client, 'docker --version 2>&1; docker compose version 2>&1 || docker-compose --version 2>&1')
        print(out.strip())
        
        # 6. 磁盘空间
        print("\n[6/6] 磁盘空间")
        out, err = run_cmd(client, "df -h / | tail -1")
        print(out.strip())
        
        # 额外：检查已有容器
        print("\n[额外] 已有项目容器")
        out, err = run_cmd(client, 'docker ps -a --filter name=6b099ed3 --format "table {{.Names}}\t{{.Status}}"')
        print(out or '(无)')
        
        print("\n" + "=" * 60)
        print("预检完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"预检失败: {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == '__main__':
    main()
