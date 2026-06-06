"""
处理后端和前端路由：去重、替换动态参数、拼接完整 URL。
"""
import re
import json

PROJECT_DOMAIN = "6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

# 后端路由（从子 Agent A 返回，按行解析）
# 由于数据量大，直接内嵌处理
backend_routes_raw = None  # 将从文件读取

# 前端路由
admin_routes = []
h5_routes = []

def parse_backend_route_line(line):
    """解析 'METHOD /path ← file:line' 格式"""
    m = re.match(r'(GET|POST|PUT|DELETE|PATCH|MOUNT)\s+(/\S+)\s+←\s+(.+):(\d+)', line.strip())
    if m:
        return {
            'method': m.group(1),
            'path': m.group(2),
            'file': m.group(3),
            'line': int(m.group(4))
        }
    return None

def parse_frontend_route_line(line):
    """解析 '[Admin] /path ← file:line' 或 '[H5] /path ← file:line' 格式"""
    m = re.match(r'\[(Admin|H5)\]\s+(/\S*)\s+←\s+(.+):(\d+)', line.strip())
    if m:
        return {
            'type': m.group(1),
            'path': m.group(2),
            'file': m.group(3),
            'line': int(m.group(4))
        }
    return None

def replace_dynamic_params(path):
    """替换动态参数为测试值"""
    # FastAPI 风格 {param}
    path = re.sub(r'\{[^}]+\}', '1', path)
    # Express/Next.js 风格 :param 或 [param]
    path = re.sub(r':\w+', '1', path)
    path = re.sub(r'\[([^\]]+)\]', '1', path)
    return path

def build_url(path, prefix=''):
    """拼接完整 HTTPS URL"""
    full_path = prefix + path
    return f"https://{PROJECT_DOMAIN}{full_path}"

print("脚本加载完成，待嵌入路由数据后执行。")
