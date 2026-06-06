import json

# Load route data
with open(r'C:\auto_output\bnbbaijkgj\all_routes_extracted.json', 'r', encoding='utf-8') as f:
    routes = json.load(f)

backend_routes = routes.get('backend', [])
frontend_routes = routes.get('frontend', [])

print(f'Backend API routes: {len(backend_routes)}')
print(f'Frontend page routes: {len(frontend_routes)}')

# Load link check results
with open(r'C:\auto_output\bnbbaijkgj\link_check_results.json', 'r', encoding='utf-8') as f:
    check_results = json.load(f)

results = check_results.get('results', [])
reachable = [r for r in results if r.get('reachable')]
unreachable = [r for r in results if not r.get('reachable')]

print(f'\nLink check - Total: {len(results)}, Reachable: {len(reachable)}, Unreachable: {len(unreachable)}')

# Check specific URLs mentioned in requirements
target_paths = [
    '/api/health/profile/member/1',
    '/api/family/member/1/unbind',
    '/api/family/management/accept',
    '/api/reverse-guardian/remove',
    '/api/devices/scene-groups',
    '/api/devices/catalog',
    '/health-profile/archive-list',
    '/health-profile/my-guardians',
    '/family-auth',
    '/messages',
    '/admin/devices/scene-groups',
    '/admin/devices/catalog',
    '/admin/',
]

print('\n=== Targeted URL checks ===')
for tp in target_paths:
    found = [r for r in results if r.get('path','') == tp]
    if found:
        r = found[0]
        print(f'  {tp}: status={r.get("status_code")}, reachable={r.get("reachable")}, classification={r.get("classification")}, error={r.get("error")}')
    else:
        print(f'  {tp}: NOT FOUND in results')

# Show all unreachable items summary
print('\n=== Unreachable URLs summary ===')
for r in unreachable:
    print(f'  [{r.get("category","?")}] {r.get("path")} | {r.get("status_code")} | {r.get("classification")} | {r.get("error","")}')
