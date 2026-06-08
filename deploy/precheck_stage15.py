"""阶段 1.5 服务器环境预检：6 项检测"""
import paramiko
import json
import sys
import time

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
WILDCARD_BASE = "noob-ai.test.bangbangvip.com"
ACR_ADDR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"
ACR_NS = "noob_doker_base"
ACR_USER = "ankun888"
ACR_PASS = "xiaobai888"
GATEWAY_CONF_DIR = "/home/ubuntu/gateway/conf.d"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

results = {}

def ssh_exec(ssh, cmd, timeout=30):
    """执行 SSH 命令并返回 stdout"""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out.strip(), err.strip(), stdout.channel.recv_exit_status()

print("=== 阶段 1.5 服务器环境预检 ===")
print(f"连接 {SSH_USER}@{SSH_HOST}:{SSH_PORT} ...")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, password=SSH_PASS, timeout=15)
    print("SSH 连接成功")
except Exception as e:
    print(f"SSH 连接失败: {e}")
    sys.exit(1)

# ========== 预检 1：Gateway nginx 配置结构探测 ==========
print("\n--- 预检 1：Gateway nginx 配置结构探测 ---")
out, err, code = ssh_exec(ssh, "cat /home/ubuntu/gateway/nginx.conf")
if code == 0:
    results['nginx_conf'] = out
    # 判断 include 位置
    lines = out.split('\n')
    in_http = False
    in_server = False
    include_line = -1
    http_start = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if 'http {' in stripped or stripped == 'http {':
            in_http = True
            http_start = i
        if 'server {' in stripped or stripped == 'server {':
            in_server = True
        if 'include conf.d/*.conf' in stripped or 'include /etc/nginx/conf.d/*.conf' in stripped:
            include_line = i
            break
    
    # 判断 include 是否在某个 server 块内
    if include_line >= 0:
        nested_server = False
        for j in range(include_line, -1, -1):
            if 'server {' in lines[j].strip() and j > http_start:
                # 检查是否已经闭合
                depth = 0
                for k in range(j, include_line + 1):
                    if '{' in lines[k]: depth += lines[k].count('{')
                    if '}' in lines[k]: depth -= lines[k].count('}')
                if depth > 0:
                    nested_server = True
                    break
        
        if nested_server:
            results['gateway_mode'] = '嵌套模式'
            results['gateway_note'] = 'include conf.d/*.conf 位于 server 块内 → conf.d 文件只能写 location 块'
        else:
            results['gateway_mode'] = '标准模式'
            results['gateway_note'] = 'include conf.d/*.conf 位于 http 块内 → conf.d 文件可写完整 server 块'
        results['include_line'] = include_line
    else:
        results['gateway_mode'] = '未知（未找到 include）'
    print(f"Gateway 模式: {results.get('gateway_mode')}")
else:
    results['gateway_mode'] = '错误：无法读取 nginx.conf'
    print(f"读取 nginx.conf 失败: {err}")

# ========== 预检 2：路由占用检查 ==========
print("\n--- 预检 2：路由占用检查 ---")
out, err, code = ssh_exec(ssh, "grep -rn 'location\\|server_name' /home/ubuntu/gateway/conf.d/ 2>/dev/null || echo 'NO_MATCHES'")
results['route_check'] = out
# 提取已有的 location 路径
import re
existing_locations = re.findall(r'location\s+([^\s{]+)', out)
results['existing_locations'] = existing_locations
print(f"已有 location 路径: {existing_locations}")

# 同时检查主 nginx.conf 中的 location
out2, err2, code2 = ssh_exec(ssh, "grep -n 'location\\|server_name' /home/ubuntu/gateway/nginx.conf 2>/dev/null")
results['nginx_locations'] = out2

conflict_warning = []
our_locations = ['/api/', '/admin/', '/']
for loc in existing_locations:
    for our_loc in our_locations:
        if loc == our_loc:
            conflict_warning.append(f"路由冲突: {loc} 已被占用！")
results['conflict_warning'] = conflict_warning
if conflict_warning:
    print(f"⚠️ 路由冲突: {conflict_warning}")
else:
    print("无路由冲突")

# ========== 预检 3：ACR 基础镜像版本匹配 ==========
print("\n--- 预检 3：ACR 基础镜像版本匹配 ---")
acr_results = {}

# 使用 Python 直接通过 API 查询 ACR
import requests
import re as re_mod

def query_acr_tags(img_name):
    """查询 ACR 中某个镜像的 tag 列表"""
    registry = ACR_ADDR
    namespace = ACR_NS
    try:
        r = requests.get(f"https://{registry}/v2/", timeout=15)
        auth_header = r.headers.get("Www-Authenticate", "")
        realm_match = re_mod.search(r'realm="([^"]+)"', auth_header)
        service_match = re_mod.search(r'service="([^"]+)"', auth_header)
        if not realm_match or not service_match:
            return []
        realm = realm_match.group(1)
        service = service_match.group(1)
        repo = f"{namespace}/{img_name}"
        params = {"service": service, "scope": f"repository:{repo}:pull"}
        tr = requests.get(realm, auth=(ACR_USER, ACR_PASS), params=params, timeout=15)
        if tr.status_code == 200:
            token = tr.json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            tr2 = requests.get(f"https://{registry}/v2/{repo}/tags/list", headers=headers, timeout=15)
            if tr2.status_code == 200:
                return sorted(tr2.json().get("tags", []))
        return []
    except Exception as e:
        return [f"ERROR: {e}"]

for img in ["python", "node", "nginx", "alpine", "redis", "mysql", "golang", "eclipse-temurin", "postgres", "maven", "mongo", "memcached"]:
    tags = query_acr_tags(img)
    acr_results[img] = tags
    print(f"  ACR {img}: {tags}")

results['acr_tags'] = acr_results

# 版本匹配
print("\nACR 版本匹配分析：")
project_needs = {
    'python': {'need': '3.12-slim', 'prefer': ['3.12-slim', '3.11-slim', '3.10-slim', '3.12', '3.11', '3.10', '3.9-slim', '3.9']},
    'node': {'need': '20-alpine', 'prefer': ['20-alpine', '18-alpine', '22-alpine', '20', '18', '22']},
}
final_images = {}
for img, info in project_needs.items():
    available = acr_results.get(img, [])
    matched = None
    matched_tag = None
    strategy = 6
    for tag in info['prefer']:
        if tag in available:
            if tag == info['need']:
                strategy = 1
            elif tag.split('-')[0] == info['need'].split('-')[0] and '-slim' in tag and '-slim' in info['need']:
                strategy = 2
            elif tag.split('-')[0] == info['need'].split('-')[0]:
                strategy = 3
            elif '-slim' in tag or '-alpine' in tag:
                strategy = 4
            else:
                strategy = 5
            matched_tag = tag
            break
    if matched_tag:
        final_images[img] = f"{ACR_ADDR}/{ACR_NS}/{img}:{matched_tag}"
        print(f"  {img}: 需求 {info['need']} → ACR 匹配 {matched_tag} (策略{strategy})")
    else:
        final_images[img] = f"{img}:{info['need']}"
        print(f"  {img}: ACR 无匹配 → 降级 Docker Hub ({img}:{info['need']})")

results['final_images'] = final_images

# ========== 预检 4：Docker 网络拓扑 ==========
print("\n--- 预检 4：Docker 网络拓扑 ---")
out, err, code = ssh_exec(ssh, "docker ps -a --filter name=gateway-nginx --format '{{.Names}} {{.Status}}' 2>&1")
results['gateway_status'] = out
print(f"Gateway 容器状态: {out}")

out, err, code = ssh_exec(ssh, "docker inspect gateway-nginx --format '{{range .NetworkSettings.Networks}}{{.Name}} {{end}}' 2>&1")
results['gateway_networks'] = out
print(f"Gateway 网络连接: {out}")

out, err, code = ssh_exec(ssh, f"docker network ls --filter name={DEPLOY_ID}-network --format '{{{{.Name}}}}' 2>&1")
results['project_network'] = out
print(f"项目网络状态: {out}")

# ========== 预检 5：基础镜像内置工具检测 ==========
print("\n--- 预检 5：基础镜像内置工具检测 ---")
tool_results = {}
for img_name, img_path in final_images.items():
    # 拉取镜像
    pull_out, pull_err, pull_code = ssh_exec(ssh, f"docker pull {img_path} 2>&1", timeout=60)
    print(f"  拉取 {img_path}: {'成功' if pull_code == 0 else '失败'}")
    # 检测工具
    if pull_code == 0:
        check_cmd = "sh -c 'which wget curl python3 node 2>/dev/null; echo DONE'"
        tool_out, tool_err, tool_code = ssh_exec(ssh, f"docker run --rm {img_path} {check_cmd} 2>&1", timeout=30)
        tool_results[img_name] = tool_out
        print(f"  {img_name} 工具: {tool_out.strip()}")
    else:
        tool_results[img_name] = f"PULL_FAILED: {pull_err}"

results['tool_check'] = tool_results

# ========== 预检 6：磁盘空间检查 ==========
print("\n--- 预检 6：磁盘空间检查 ---")
out, err, code = ssh_exec(ssh, "df -h / | tail -1")
results['disk_space'] = out
print(f"磁盘空间: {out}")

# ========== 汇总 ==========
print("\n" + "="*60)
print("预检结果汇总")
print("="*60)

# 打印关键决策
print(f"\nGateway 模式: {results.get('gateway_mode')}")
print(f"路由冲突: {results.get('conflict_warning', '无')}")
print(f"最终镜像: {final_images}")
print(f"Gateway 容器: {results.get('gateway_status')}")
print(f"项目网络: {results.get('project_network')}")
print(f"磁盘: {results.get('disk_space')}")

# 保存结果
with open('C:/auto_output/bnbbaijkgj/deploy/precheck_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)

print("\n预检结果已保存到 deploy/precheck_results.json")

ssh.close()
print("SSH 已断开")
print("\n✅ 阶段 1.5 预检完成")
