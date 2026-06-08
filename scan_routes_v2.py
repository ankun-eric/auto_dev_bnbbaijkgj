"""
扫描测试服务器后端 API 路由，生成完整 API 端点清单。
通过 paramiko SSH/SFTP 连接到远程服务器，解析 FastAPI 路由定义。
"""
import paramiko
import re
import os
import posixpath

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/backend"
API_DIR = posixpath.join(PROJECT_DIR, "app", "api")
MAIN_FILE = posixpath.join(PROJECT_DIR, "app", "main.py")
OUTPUT_FILE = r"C:\auto_output\bnbbaijkgj\deploy\backend_routes_prod.txt"


def read_remote_file_safe(sftp, path):
    """安全读取远程文件，失败返回空字符串。"""
    try:
        with sftp.open(path, "r") as f:
            return f.read().decode("utf-8")
    except Exception as e:
        print(f"  [跳过] 无法读取: {path} ({e})")
        return ""


def extract_routes(content):
    """
    从文件内容中提取所有路由定义。
    支持单行和多行装饰器：
      @router.get("/path")
      @router.post("/path")
      @app.get("/path")
      @router.websocket("/ws")
    也支持多行变体：
      @router.get(
          "/path"
      )
    返回列表 [(method, path), ...]
    """
    routes = []

    # 策略：先把多行装饰器压缩到一行
    # 找到 @router.xxx( 或 @app.xxx( 开始的位置，直到遇到下一个 @ 或 def/class
    # 简单做法：移除装饰器参数中的换行
    def collapse_multiline(m):
        body = m.group(0)
        return body.replace('\n', ' ')

    # 将 @router.xxx(\n...\n) 中的换行替换为空格
    # 匹配从 @ 开始到匹配的 ) 结束
    content = re.sub(
        r'@(?:router|app)\.\w+\s*\([^)]*\)',
        lambda m: m.group(0).replace('\n', ' ').replace('\r', ''),
        content
    )
    # 但上面的正则无法匹配嵌套括号。对于路由装饰器，通常不会有嵌套括号。
    # 对于跨行的情况，上面的处理可能不够。改用更激进的方式：

    # 更简单：逐行扫描
    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # 匹配装饰器开始
        m = re.match(r'@(?P<obj>router|app)\.(?P<method>get|post|put|delete|patch|options|head|websocket)\s*\(\s*["\'](?P<path>[^"\']*)["\']\s*\)', line)
        if m:
            method = m.group("method").upper()
            path = m.group("path")
            routes.append((method, path))
            i += 1
            continue

        # 匹配多行装饰器：@router.xxx( 后面可能没有立即跟路径
        m2 = re.match(r'@(?P<obj>router|app)\.(?P<method>get|post|put|delete|patch|options|head|websocket)\s*\(\s*$', line)
        if m2:
            method = m2.group("method").upper()
            # 收集后续行直到找到路径或闭合括号
            j = i + 1
            combined = ""
            while j < len(lines):
                combined += " " + lines[j].strip()
                # 查找路径
                path_m = re.search(r'["\']([^"\']*)["\']', combined)
                if path_m:
                    path = path_m.group(1)
                    routes.append((method, path))
                    break
                if ')' in combined:
                    break
                j += 1
            i = j + 1
            continue

        i += 1

    return routes


def extract_router_prefixes(content):
    """
    从 main.py 提取 include_router 的 prefix。
    示例: app.include_router(family.router, prefix="/api/family")
    返回 prefix 列表。
    """
    prefixes = []
    pattern = r'\.include_router\s*\([^)]*?prefix\s*=\s*["\']([^"\']+)["\']'
    for m in re.finditer(pattern, content):
        prefixes.append(m.group(1))
    return prefixes


def replace_dynamic_params(path):
    """将 {param} 和 {param:type} 替换为 '1'。"""
    path = re.sub(r'\{[^}:]+:[^}]+\}', '1', path)
    path = re.sub(r'\{[^}]+\}', '1', path)
    return path


def main():
    print("连接 SSH...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()
    print("已连接。")

    # 1. 列出 API 目录文件（仅第一层，不递归）
    print(f"\n列出 {API_DIR} ...")
    try:
        items = sftp.listdir_attr(API_DIR)
    except Exception as e:
        print(f"无法列出目录: {e}")
        sftp.close()
        client.close()
        return

    api_files = []
    for item in items:
        if item.filename.endswith('.py') and item.filename != '__init__.py':
            api_files.append(posixpath.join(API_DIR, item.filename))

    print(f"找到 {len(api_files)} 个 .py 文件")

    # 2. 读取 main.py
    print(f"\n读取 main.py ...")
    main_content = read_remote_file_safe(sftp, MAIN_FILE)

    prefixes = extract_router_prefixes(main_content)
    print(f"提取到 {len(prefixes)} 个 router prefix:")
    for p in prefixes:
        print(f"  {p}")

    # 3. 提取每个文件的路由
    print(f"\n提取路由...")
    all_routes = []  # (method, path)

    for fpath in sorted(api_files):
        fname = posixpath.basename(fpath)
        content = read_remote_file_safe(sftp, fpath)
        if not content:
            continue
        routes = extract_routes(content)
        for method, path in routes:
            all_routes.append((method, path))
        if routes:
            print(f"  {fname}: {len(routes)} 条路由")

    # 4. 也从 main.py 提取路由
    if main_content:
        main_routes = extract_routes(main_content)
        for method, path in main_routes:
            all_routes.append((method, path))
        if main_routes:
            print(f"  main.py: {len(main_routes)} 条路由")

    sftp.close()
    client.close()
    print("\nSSH 连接已关闭。")

    # 5. 去重 + 替换动态参数
    unique = {}
    for method, path in all_routes:
        if not path or not path.strip():
            continue
        resolved = replace_dynamic_params(path)
        if not resolved or not resolved.strip() or resolved == '/':
            continue
        key = (method, resolved)
        if key not in unique:
            unique[key] = path

    # 6. 排序
    sorted_routes = sorted(unique.keys(), key=lambda x: (x[1], x[0]))

    # 7. 输出
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for method, path in sorted_routes:
            label = "WS" if method == "WEBSOCKET" else method
            f.write(f"{label} {path}\n")

    print(f"\n去重后共 {len(sorted_routes)} 个端点")
    print(f"输出到: {OUTPUT_FILE}")

    # 打印清单
    print("\n========== API 端点清单 ==========")
    for method, path in sorted_routes:
        label = "WS" if method == "WEBSOCKET" else method
        print(f"  {label} {path}")


if __name__ == "__main__":
    main()
