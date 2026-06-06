"""
Phase 1.5: Server environment precheck via paramiko SSH.
"""
import paramiko
import sys

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def ssh_exec(ssh, cmd, timeout=30):
    """Execute command and return (stdout, stderr, exit_code)."""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
        print("=== SSH 连接成功 ===")
    except Exception as e:
        print(f"SSH 连接失败: {e}")
        sys.exit(1)

    results = {}

    # === Precheck 1: Gateway nginx config structure ===
    print("\n=== 预检 1: Gateway nginx 配置结构 ===")
    out, err, _ = ssh_exec(ssh, "cat /home/ubuntu/gateway/nginx.conf")
    print(out[:2000])
    # Determine gateway mode
    if 'include conf.d/*.conf;' in out:
        # Check if include is in http block or inside a server block
        lines = out.split('\n')
        in_http = False
        in_server = False
        include_in_server = False
        include_in_http = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('http'):
                in_http = True
            if 'server {' in stripped and in_http:
                in_server = True
            if 'include conf.d/*.conf' in stripped:
                if in_server:
                    include_in_server = True
                elif in_http:
                    include_in_http = True
        if include_in_server:
            results['gateway_mode'] = 'nested'
            print("→ Gateway 模式: 嵌套模式 (include 在 server 块内)")
        else:
            results['gateway_mode'] = 'standard'
            print("→ Gateway 模式: 标准模式 (include 在 http 块内)")
    else:
        # Check for wildcard server_name
        if 'server_name _' in out or 'server_name *' in out:
            results['gateway_mode'] = 'standard'
            print("→ Gateway 模式: 标准模式")
        else:
            results['gateway_mode'] = 'unknown'
            print("→ Gateway 模式: 未知")

    # === Precheck 2: Route occupancy ===
    print("\n=== 预检 2: 路由占用检查 ===")
    out, err, _ = ssh_exec(ssh, "grep -rn 'location\|server_name' /home/ubuntu/gateway/conf.d/ 2>/dev/null || echo 'no_confd'")
    print(out[:2000])
    results['confd_routes'] = out

    out2, err2, _ = ssh_exec(ssh, "grep -n 'location\|server_name' /home/ubuntu/gateway/nginx.conf 2>/dev/null")
    print(out2[:1000])
    results['nginx_routes'] = out2

    # === Precheck 3: ACR images ===
    print("\n=== 预检 3: ACR 基础镜像版本 ===")
    out, err, _ = ssh_exec(ssh, """
for img in python node nginx alpine mysql; do
  case $img in
    python) tags="3.12-slim 3.11-slim 3.10-slim 3.12 3.11 3.10 3.9-slim 3.9" ;;
    node)   tags="20-alpine 22-alpine 18-alpine 20 22 18" ;;
    nginx)  tags="alpine latest" ;;
    alpine) tags="3.19 3.18 3.17" ;;
    mysql)  tags="8.0 8.0-oracle" ;;
  esac
  for tag in $tags; do
    result=$(docker manifest inspect crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/$img:$tag 2>&1)
    if [ $? -eq 0 ]; then
      echo "FOUND: crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/$img:$tag"
    fi
  done
done
""", timeout=45)
    print(out)
    results['acr_images'] = out

    # === Precheck 4: Docker network ===
    print("\n=== 预检 4: Docker 网络拓扑 ===")
    out, err, _ = ssh_exec(ssh, "docker ps -a --filter name=gateway-nginx --format '{{.Names}} {{.Status}}'")
    print(f"gateway-nginx: {out}")
    results['gateway_status'] = out

    out, err, _ = ssh_exec(ssh, f"docker network ls --filter name={DEPLOY_ID}-network --format '{{.Name}}'")
    print(f"项目网络: {out}")
    results['project_network'] = out

    # === Precheck 5: Image tools ===
    print("\n=== 预检 5: 基础镜像工具检测 ===")
    out, err, _ = ssh_exec(ssh, "docker run --rm crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/python:3.12-slim sh -c 'which wget curl python3 2>/dev/null'", timeout=60)
    print(f"Python slim tools: {out}")
    results['py_tools'] = out

    out, err, _ = ssh_exec(ssh, "docker run --rm crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/node:20-alpine sh -c 'which wget curl node 2>/dev/null'", timeout=60)
    print(f"Node alpine tools: {out}")
    results['node_tools'] = out

    # === Precheck 6: Disk space ===
    print("\n=== 预检 6: 磁盘空间 ===")
    out, err, _ = ssh_exec(ssh, "df -h / | tail -1")
    print(out)
    results['disk'] = out

    ssh.close()
    print("\n=== 预检完成 ===")
    print(f"汇总: gateway_mode={results.get('gateway_mode')}")

if __name__ == "__main__":
    main()
