"""
扫描测试服务器后端 API 路由，生成完整 API 端点清单。
通过 paramiko SSH 连接到远程服务器，解析 FastAPI 路由定义。
"""

import paramiko
import re
import os
import posixpath

# SSH 配置
HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/backend"
API_DIR = posixpath.join(PROJECT_DIR, "app", "api")
MAIN_FILE = posixpath.join(PROJECT_DIR, "app", "main.py")
OUTPUT_FILE = r"C:\auto_output\bnbbaijkgj\deploy\backend_routes_prod.txt"


def ssh_connect():
    """建立 SSH 连接并返回 SFTP 客户端。"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    return client


def list_api_files(sftp):
    """列出 API 目录下所有 .py 文件（递归）。"""
    files = []
    try:
        items = sftp.listdir_attr(API_DIR)
    except FileNotFoundError:
        print(f"警告: 目录 {API_DIR} 不存在")
        return files

    # 递归遍历
    def walk(remote_dir):
        try:
            for item in sftp.listdir_attr(remote_dir):
                full_path = posixpath.join(remote_dir, item.filename)
                if item.filename.startswith("."):
                    continue
                if item.filename.startswith("__"):
                    # 跳过 __pycache__ 和 __init__.py 读取（但 __init__.py 可能也有路由）
                    if item.filename == "__pycache__":
                        continue
                if stat_mode_is_dir(item.st_mode):
                    walk(full_path)
                elif item.filename.endswith(".py"):
                    files.append(full_path)
        except IOError:
            pass

    walk(API_DIR)
    return files


def stat_mode_is_dir(mode):
    """判断 stat mode 是否为目录（paramiko 在不同平台行为不同）。"""
    import stat
    return stat.S_ISDIR(mode)


def read_remote_file(sftp, path):
    """读取远程文件内容。"""
    try:
        with sftp.open(path, "r") as f:
            return f.read().decode("utf-8")
    except Exception as e:
        print(f"读取文件失败: {path}, 错误: {e}")
        return ""


def extract_routes_from_content(content, filename):
    """
    从文件内容中提取路由定义。
    支持 @router.get/post/put/delete/patch 和 @app.get 等装饰器。
    返回列表 [(method, path), ...]
    """
    routes = []
    # 匹配 @router.method("path") 或 @app.method("path")
    # 也匹配多行装饰器（如 @router.get(\n    "/path")）
    
    # 将内容中换行的装饰器参数合并到一行
    # 先处理多行装饰器
    normalized = re.sub(r'@(router|app)\.(get|post|put|delete|patch|options|head)\s*\(\s*\n', 
                        lambda m: m.group(0).replace('\n', ' '), content)
    
    # 匹配模式: @router.xxx("path") 或 @app.xxx("path")
    pattern = r'@(?P<obj>router|app)\.(?P<method>get|post|put|delete|patch|options|head|websocket)\s*\(\s*["\'](?P<path>[^"\']+)["\']'
    
    for m in re.finditer(pattern, normalized):
        method = m.group("method").upper()
        path = m.group("path")
        routes.append((method, path))
    
    return routes


def extract_router_prefixes_from_main(content):
    """
    从 main.py 中提取 router prefix。
    查找 app.include_router(xxx, prefix="...") 模式。
    返回列表 [(router_var, prefix), ...]
    """
    prefixes = []
    # 匹配 include_router 调用
    pattern = r'(?:app|main_app)\.include_router\s*\([^)]*?prefix\s*=\s*["\']([^"\']+)["\']'
    for m in re.finditer(pattern, content):
        prefixes.append(m.group(1))
    return prefixes


def replace_dynamic_params(path):
    """
    将动态路径参数替换为合理测试值。
    {param} -> 1 或 test
    {param:type} -> 匹配的类型默认值
    """
    # 替换各种动态参数模式
    # {param} -> 1
    path = re.sub(r'\{[^}:]+:[^}]+\}', '1', path)  # {param:type}
    path = re.sub(r'\{[^}]+\}', '1', path)          # {param}
    return path


def is_websocket_route(method, path):
    """判断是否为 WebSocket 路由。"""
    return method == "WEBSOCKET"


def main():
    print("正在连接 SSH...")
    client = ssh_connect()
    sftp = client.open_sftp()
    
    all_routes = []
    
    # 1. 扫描 API 目录下的所有 .py 文件
    print("正在扫描 API 文件...")
    api_files = list_api_files(sftp)
    print(f"找到 {len(api_files)} 个 API 文件:")
    for f in api_files:
        print(f"  {f}")
    
    # 2. 读取 main.py 获取 router prefixes
    print("\n正在读取 main.py...")
    main_content = read_remote_file(sftp, MAIN_FILE)
    router_prefixes = extract_router_prefixes_from_main(main_content)
    print(f"找到 {len(router_prefixes)} 个 router prefix:")
    for p in router_prefixes:
        print(f"  {p}")
    
    # 3. 读取每个 API 文件并提取路由
    print("\n正在提取路由...")
    for file_path in sorted(api_files):
        content = read_remote_file(sftp, file_path)
        if not content:
            continue
        routes = extract_routes_from_content(content, file_path)
        for method, path in routes:
            full_path = path
            all_routes.append((method, full_path))
            print(f"  {method} {full_path}")
    
    # 4. 也直接从 main.py 提取路由
    print("\n正在从 main.py 提取直接路由...")
    main_routes = extract_routes_from_content(main_content, "main.py")
    for method, path in main_routes:
        all_routes.append((method, path))
        print(f"  {method} {path}")
    
    sftp.close()
    client.close()
    
    # 5. 去重并整理
    unique_routes = {}
    for method, path in all_routes:
        # 替换动态参数
        resolved_path = replace_dynamic_params(path)
        key = (method, resolved_path)
        if key not in unique_routes:
            unique_routes[key] = path  # 保留原始路径用于参考
    
    # 6. 排序并输出
    sorted_routes = sorted(unique_routes.keys(), key=lambda x: (x[1], x[0]))
    
    # 写入文件
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for method, path in sorted_routes:
            if method == "WEBSOCKET" or method == "WS":
                f.write(f"WS {path}\n")
            else:
                f.write(f"{method} {path}\n")
    
    print(f"\n总共 {len(sorted_routes)} 个唯一路由端点。")
    print(f"结果已写入: {OUTPUT_FILE}")
    
    # 同时打印到控制台
    print("\n========== 完整路由清单 ==========")
    for method, path in sorted_routes:
        label = "WS" if method in ("WEBSOCKET", "WS") else method
        print(f"  {label} {path}")


if __name__ == "__main__":
    main()
