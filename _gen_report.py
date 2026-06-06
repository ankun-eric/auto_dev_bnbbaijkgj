import json

with open(r'C:\auto_output\bnbbaijkgj\link_check_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

results = data.get('results', [])
total = len(results)
reachable = [r for r in results if r.get('reachable')]
unreachable = [r for r in results if not r.get('reachable')]

print(f"Total URLs: {total}")
print(f"Reachable: {len(reachable)} ({100*len(reachable)/total:.1f}%)")
print(f"Unreachable: {len(unreachable)} ({100*len(unreachable)/total:.1f}%)")

# Classify unreachable
deploy_issues = []
dev_issues = []

for r in unreachable:
    path = r.get('path', '')
    cat = r.get('category', '')
    status = r.get('status_code', 0)
    classification = r.get('classification', '')
    
    # /api/admin/api/... double prefix - dev issue
    if path.startswith('/api/admin/api/'):
        dev_issues.append({
            'type': '/api/api/ 重复前缀',
            'url': path,
            'status': status,
            'cat': cat,
            'classification': classification
        })
    # Frontend page timeout
    elif cat in ('H5', 'Admin') and classification == 'UNKNOWN_0':
        deploy_issues.append({
            'type': '前端页面超时',
            'url': path,
            'status': status,
            'cat': cat,
            'classification': classification
        })
    # Backend API timeout
    elif cat == 'Backend' and classification == 'UNKNOWN_0':
        deploy_issues.append({
            'type': '后端 API 超时',
            'url': path,
            'status': status,
            'cat': cat,
            'classification': classification
        })
    # Backend 404 (not double-prefix)
    elif classification == '404':
        deploy_issues.append({
            'type': 'API 返回 404',
            'url': path,
            'status': status,
            'cat': cat,
            'classification': classification
        })
    else:
        deploy_issues.append({
            'type': f'其他 ({classification})',
            'url': path,
            'status': status,
            'cat': cat,
            'classification': classification
        })

print(f"\n=== 部署问题 ({len(deploy_issues)}) ===")
for i, issue in enumerate(deploy_issues, 1):
    print(f"  {i}. [{issue['type']}] {issue['url']} (status={issue['status']})")

print(f"\n=== 开发问题 ({len(dev_issues)}) ===")
for i, issue in enumerate(dev_issues, 1):
    print(f"  {i}. [{issue['type']}] {issue['url']} (status={issue['status']})")
