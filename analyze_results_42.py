import json

data = json.load(open('link_check_results.json', 'r', encoding='utf-8'))
unreachable = [r for r in data['results'] if not r['reachable']]

# 分类
admin_api_double = []  # /api/admin/api/... 路径（可能误报）
page_404 = []  # 前端页面 404
api_404 = []  # API 404（非双前缀）
timeout_0 = []  # 超时
page_timeout = []  # 前端页面超时

for r in unreachable:
    path = r['path']
    cls = r['classification']
    is_page = r['type'] == 'PAGE'
    
    if cls == 'UNKNOWN_0':
        if is_page:
            page_timeout.append(r)
        else:
            timeout_0.append(r)
    elif '/api/admin/api/' in path:
        admin_api_double.append(r)
    elif cls == '404':
        if is_page:
            page_404.append(r)
        else:
            api_404.append(r)
    else:
        if is_page:
            page_404.append(r)
        else:
            api_404.append(r)

with open('unreachable_analysis.txt', 'w', encoding='utf-8') as f:
    f.write(f"不可达总数: {len(unreachable)}\n")
    f.write(f"  前端页面404: {len(page_404)}\n")
    f.write(f"  前端页面超时: {len(page_timeout)}\n")
    f.write(f"  API 404 (真实): {len(api_404)}\n")
    f.write(f"  API 双/api/前缀 404 (可能命名问题): {len(admin_api_double)}\n")
    f.write(f"  API 超时: {len(timeout_0)}\n\n")
    
    f.write("=== 前端页面 404 ===\n")
    for r in page_404:
        f.write(f"  [{r['category']}] {r['path']}\n")
    
    f.write("\n=== 前端页面 超时 ===\n")
    for r in page_timeout:
        f.write(f"  [{r['category']}] {r['path']}\n")
    
    f.write(f"\n=== API 404 (真实, 共{len(api_404)}条) ===\n")
    for r in api_404[:50]:
        f.write(f"  {r['path']}\n")
    
    f.write(f"\n=== API 双/api/前缀 404 (共{len(admin_api_double)}条, 可能路由命名问题) ===\n")
    for r in admin_api_double[:30]:
        f.write(f"  {r['path']}\n")
    
    f.write(f"\n=== API 超时 (共{len(timeout_0)}条) ===\n")
    for r in timeout_0:
        f.write(f"  {r['path']}\n")

print("分析完成，写入 unreachable_analysis.txt")
print(f"总不可达: {len(unreachable)}")
print(f"  前端页面404: {len(page_404)}")
print(f"  前端页面超时: {len(page_timeout)}")
print(f"  API 404 (真实): {len(api_404)}")
print(f"  API 双/api/前缀: {len(admin_api_double)}")
print(f"  API 超时: {len(timeout_0)}")
