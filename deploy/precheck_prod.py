#!/usr/bin/env python3
"""阶段1.5：生产服务器环境预检脚本"""
import paramiko, json, time

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ACR_REGISTRY = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_NS = "noob_doker_base"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"

def ssh_exec(ssh, cmd, timeout=30):
    """执行SSH命令并返回输出"""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out.strip(), err.strip()

def connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
    return ssh

results = {}

try:
    ssh = connect()
    print("SSH连接成功")
    
    # === 预检1: Gateway nginx 配置结构 ===
    print("\n=== 预检1: Gateway nginx 配置结构 ===")
    rc, nginx_conf, err = ssh_exec(ssh, "cat /home/ubuntu/gateway/nginx.conf 2>/dev/null || echo 'NOT_FOUND'")
    results["nginx_conf"] = nginx_conf[:8000]
    
    if "include conf.d/*.conf;" in nginx_conf:
        if "conf.d/*.conf;" in nginx_conf.split("server {")[0] if "server {" in nginx_conf else False:
            results["gateway_mode"] = "标准模式"
            results["gateway_note"] = "include conf.d/*.conf 在 http 块内 → conf.d 文件应包含完整 server 块"
        else:
            results["gateway_mode"] = "嵌套模式"
            results["gateway_note"] = "include conf.d/*.conf 位于 server 块内"
    else:
        results["gateway_mode"] = "未知/自定义"
        results["gateway_note"] = "未找到 include conf.d/*.conf"
    print(f"Gateway模式: {results['gateway_mode']}")

    # === 预检2: 路由占用检查 ===
    print("\n=== 预检2: 路由占用检查 ===")
    rc, route_check, err = ssh_exec(ssh, "grep -rn 'location\|server_name' /home/ubuntu/gateway/conf.d/ 2>/dev/null | head -80")
    results["route_check"] = route_check[:3000]
    
    rc, nginx_locations, err = ssh_exec(ssh, "grep -n 'location\|server_name' /home/ubuntu/gateway/nginx.conf 2>/dev/null")
    results["nginx_locations"] = nginx_locations[:3000]
    print(f"路由检查完成, route_check长度={len(route_check)}")

    # === 预检3: ACR 基础镜像检查（在服务器上执行） ===
    print("\n=== 预检3: ACR 基础镜像检查 ===")
    acr_cmd = """docker login --username=ankun888 --password=xiaobai888 crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com 2>&1 && echo 'ACR_LOGIN_OK'"""
    rc, acr_login, err = ssh_exec(ssh, acr_cmd)
    print(f"ACR登录: {acr_login[-50:]}")
    
    acr_tags = {}
    for img in ["python", "node", "nginx", "alpine", "memcached", "redis", "golang", "eclipse-temurin", "postgres", "maven", "mongo", "mysql"]:
        rc, out, err = ssh_exec(ssh, f"docker manifest inspect crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/{img}:latest 2>&1 | head -5")
        if rc == 0:
            acr_tags[img] = ["latest (exists)"]
        else:
            acr_tags[img] = ["unknown (manifest failed)"]
    
    # 精确检查项目需要的版本
    project_images = {
        "python": ["3.12-slim", "3.11-slim", "3.10-slim"],
        "node": ["20-alpine", "22-alpine", "18-alpine"],
    }
    final_images = {}
    for img, tags in project_images.items():
        found = False
        for tag in tags:
            rc, out, err = ssh_exec(ssh, f"docker manifest inspect crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/{img}:{tag} 2>&1 | head -3")
            if rc == 0:
                final_images[img] = f"crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/{img}:{tag}"
                acr_tags[img] = [tag]
                found = True
                print(f"  找到 ACR {img}:{tag}")
                break
        if not found:
            final_images[img] = f"{img}:{tags[0]}"
            print(f"  ACR 无 {img}，降级到 Docker Hub: {tags[0]}")
    
    results["acr_tags"] = acr_tags
    results["final_images"] = final_images

    # === 预检4: Docker 网络拓扑 ===
    print("\n=== 预检4: Docker 网络拓扑 ===")
    rc, gw_status, err = ssh_exec(ssh, "docker ps -a --filter name=gateway-nginx --format '{{.Names}} {{.Status}}' 2>/dev/null || echo 'NOT_FOUND'")
    results["gateway_status"] = gw_status
    print(f"Gateway状态: {gw_status}")
    
    rc, gw_networks, err = ssh_exec(ssh, "docker inspect gateway-nginx --format '{{range .NetworkSettings.Networks}}{{.Name}} {{end}}' 2>/dev/null || echo 'NOT_FOUND'")
    results["gateway_networks"] = gw_networks
    print(f"Gateway网络: {gw_networks}")
    
    rc, proj_net, err = ssh_exec(ssh, f"docker network ls --filter name={DEPLOY_ID}-network --format '{{{{.Name}}}}' 2>/dev/null || echo 'NOT_FOUND'")
    results["project_network"] = proj_net
    print(f"项目网络: {proj_net}")

    # === 预检5: 基础镜像工具检测 ===
    print("\n=== 预检5: 基础镜像工具检测 ===")
    tool_check = {}
    if "python" in final_images:
        rc, out, err = ssh_exec(ssh, f"docker run --rm {final_images['python']} sh -c 'which python3 wget curl 2>&1' 2>&1")
        tool_check["python"] = out[:500]
        print(f"Python工具: {out[:200]}")
    if "node" in final_images:
        rc, out, err = ssh_exec(ssh, f"docker run --rm {final_images['node']} sh -c 'which node wget curl 2>&1' 2>&1")
        tool_check["node"] = out[:500]
        print(f"Node工具: {out[:200]}")
    results["tool_check"] = tool_check

    # === 预检6: 磁盘空间 ===
    print("\n=== 预检6: 磁盘空间 ===")
    rc, disk, err = ssh_exec(ssh, "df -h / | tail -1")
    results["disk_space"] = disk
    print(f"磁盘空间: {disk}")
    
    ssh.close()
    print("\n所有预检完成")

except Exception as e:
    results["error"] = str(e)
    print(f"预检失败: {e}")

# 保存结果
with open("deploy/precheck_results_prod.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n预检结果已保存到 deploy/precheck_results_prod.json")
print(f"关键发现:")
print(f"  Gateway模式: {results.get('gateway_mode', 'N/A')}")
print(f"  最终镜像: {results.get('final_images', {})}")
print(f"  Gateway状态: {results.get('gateway_status', 'N/A')}")
print(f"  磁盘: {results.get('disk_space', 'N/A')}")
