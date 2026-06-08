"""
扫描测试服务器后端 API 路由，生成完整 API 端点清单 v3。
改进：
- 使用 exec_command 在远程执行 Python 脚本提取路由（更快、更准确）
- 直接从远程路由模块获取 prefix
- 过滤空路径和无意义路径
"""
import paramiko
import re
import os
import posixpath
import json

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/backend"
OUTPUT_FILE = r"C:\auto_output\bnbbaijkgj\deploy\backend_routes_prod.txt"


def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    return client


def exec_remote_script(client, script_content):
    """
    在远程服务器上执行 Python 脚本并返回 stdout。
    通过写入临时文件并执行的方式避免转义问题。
    """
    # 将脚本写入远程临时文件
    tmp_path = "/tmp/scan_routes_temp.py"
    sftp = client.open_sftp()
    with sftp.open(tmp_path, "w") as f:
        f.write(script_content)
    sftp.close()

    stdin, stdout, stderr = client.exec_command(f"cd {PROJECT_DIR} && python3 {tmp_path}")
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    
    # 清理临时文件
    client.exec_command(f"rm -f {tmp_path}")
    
    if err:
        print(f"[stderr]: {err[:500]}")
    return out


def main():
    print("连接 SSH...")
    client = ssh_connect()
    print("已连接。")

    # 在远程服务器上执行扫描脚本
    remote_script = r'''
import os
import re
import ast
import sys
import json

api_dir = os.path.join(os.path.dirname(__file__), "app", "api")
main_file = os.path.join(os.path.dirname(__file__), "app", "main.py")

results = []

def extract_routes_from_file(filepath):
    """从文件中提取路由定义，返回 [(method, full_path, source_file)]"""
    routes = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return routes

    fname = os.path.basename(filepath)

    # 首先尝试提取 router = APIRouter(prefix="...")
    router_prefix = ""
    prefix_match = re.search(r'APIRouter\s*\([^)]*?prefix\s*=\s*["\']([^"\']+)["\']', content)
    if prefix_match:
        router_prefix = prefix_match.group(1)
    
    # 也尝试 admin_router = APIRouter(prefix="...")
    # 已经包含在上面的匹配中

    # 提取路由装饰器中的路径
    # 策略：逐行扫描 + 多行合并
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 单行装饰器: @router.get("/path") 或 @app.get("/path")
        m = re.match(
            r'@(?P<obj>router|admin_router|user_router|public_router|'
            r'partner_router|new_user_router|staff_router|'
            r'order_card_router|product_card_router|'
            r'poster_router|settings_router|goods_tags_router|'
            r'recommend_router|audit_phone_router|audit_router|'
            r'app|_med_plan_alias_router)'
            r'\.(?P<method>get|post|put|delete|patch|options|head|websocket)'
            r'\s*\(\s*["\'](?P<path>[^"\']*)["\']',
            line
        )
        if m:
            method = m.group("method").upper()
            path = m.group("path")
            if path:  # 过滤空路径
                full_path = router_prefix.rstrip("/") + "/" + path.lstrip("/") if router_prefix else path
                full_path = full_path.replace("//", "/")
                routes.append((method, full_path, fname))
            i += 1
            continue
        
        # 多行装饰器: @router.get(\n    "/path"\n)
        m2 = re.match(
            r'@(?P<obj>router|admin_router|user_router|public_router|'
            r'partner_router|new_user_router|staff_router|'
            r'order_card_router|product_card_router|'
            r'poster_router|settings_router|goods_tags_router|'
            r'recommend_router|audit_phone_router|audit_router|'
            r'app)'
            r'\.(?P<method>get|post|put|delete|patch|options|head|websocket)\s*\(\s*$',
            line
        )
        if m2:
            method = m2.group("method").upper()
            # 查找后续行中的路径
            j = i + 1
            while j < len(lines) and j < i + 10:
                combined = lines[j].strip()
                pm = re.search(r'["\']([^"\']+)["\']', combined)
                if pm:
                    path = pm.group(1)
                    if path:
                        full_path = router_prefix.rstrip("/") + "/" + path.lstrip("/") if router_prefix else path
                        full_path = full_path.replace("//", "/")
                        routes.append((method, full_path, fname))
                    break
                if ')' in combined:
                    break
                j += 1
            i = j + 1
            continue
        
        i += 1
    
    return routes


# 扫描所有 API 文件
api_files = []
if os.path.isdir(api_dir):
    for f in sorted(os.listdir(api_dir)):
        if f.endswith('.py') and f != '__init__.py':
            api_files.append(os.path.join(api_dir, f))

# 提取每个文件的路由
for fpath in api_files:
    routes = extract_routes_from_file(fpath)
    results.extend(routes)

# 也扫描 main.py
if os.path.exists(main_file):
    routes = extract_routes_from_file(main_file)
    results.extend(routes)

# 去重
seen = set()
unique = []
for method, path, src in results:
    key = (method, path)
    if key not in seen:
        seen.add(key)
        unique.append((method, path, src))

# 排序
unique.sort(key=lambda x: (x[1], x[0]))

# 输出 JSON
print(json.dumps(unique, ensure_ascii=False))
'''

    print("在远程执行扫描脚本...")
    output = exec_remote_script(client, remote_script)
    
    # 解析 JSON 输出
    try:
        # 找到 JSON 数组的起始位置
        json_start = output.find('[')
        if json_start >= 0:
            json_str = output[json_start:]
            routes_data = json.loads(json_str)
        else:
            print("未找到 JSON 输出，原始输出:")
            print(output[:1000])
            routes_data = []
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        print("原始输出前 2000 字符:")
        print(output[:2000])
        routes_data = []

    client.close()
    print(f"\n提取到 {len(routes_data)} 个路由端点。")

    # 替换动态参数
    def replace_dynamic_params(path):
        path = re.sub(r'\{[^}:]+:[^}]+\}', '1', path)
        path = re.sub(r'\{[^}]+\}', '1', path)
        return path

    # 去重（再次）
    seen = set()
    final_routes = []
    for method, path, src in routes_data:
        resolved = replace_dynamic_params(path)
        # 过滤空路径
        if not resolved or resolved == '/':
            continue
        key = (method, resolved)
        if key not in seen:
            seen.add(key)
            final_routes.append((method, resolved))

    # 排序
    final_routes.sort(key=lambda x: (x[1], x[0]))

    # 写入文件
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for method, path in final_routes:
            label = "WS" if method == "WEBSOCKET" else method
            f.write(f"{label} {path}\n")

    print(f"去重后共 {len(final_routes)} 个端点。")
    print(f"输出到: {OUTPUT_FILE}")

    # 打印前 50 行预览
    print("\n========== 前 50 条 ==========")
    for method, path in final_routes[:50]:
        label = "WS" if method == "WEBSOCKET" else method
        print(f"  {label} {path}")
    
    if len(final_routes) > 50:
        print(f"  ... 还有 {len(final_routes) - 50} 条")


if __name__ == "__main__":
    main()
