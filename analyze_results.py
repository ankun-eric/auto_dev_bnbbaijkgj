import json

with open('url_check_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

def analyze(label, results):
    ok_200 = [r for r in results if r.get('final_status') == 200 or r.get('direct_status') == 200]
    redirect = [r for r in results if r.get('direct_status') in (301, 302, 307, 308)]
    not_found = [r for r in results if r.get('final_status') == 404 or r.get('direct_status') == 404]
    errors = [r for r in results if r.get('error')]
    other = [r for r in results if r not in ok_200 + redirect + not_found + errors]
    
    print(f'{label}:')
    print(f'  200 OK: {len(ok_200)}')
    print(f'  30x redirect: {len(redirect)}')
    print(f'  404: {len(not_found)}')
    print(f'  Error: {len(errors)}')
    print(f'  Other: {len(other)}')
    
    if not_found:
        print(f'  404 details:')
        for r in not_found:
            print(f'    {r["url"]}')
    if errors:
        print(f'  Error details:')
        for r in errors:
            print(f'    {r["url"]}: {r["error"]}')
    if other:
        print(f'  Other details:')
        for r in other[:15]:
            print(f'    {r["url"]}: direct={r.get("direct_status")} final={r.get("final_status")}')
    return ok_200, redirect, not_found, errors, other

print("=" * 60)
print("H5 前端页面分析")
print("=" * 60)
h5 = data.get('round2_h5', [])
analyze("H5", h5)

print("\n" + "=" * 60)
print("Admin 前端页面分析")
print("=" * 60)
admin = data.get('round3_admin', [])
analyze("Admin", admin)

print("\n" + "=" * 60)
print("API 抽样分析")
print("=" * 60)
api = data.get('round4_api_sample', [])
ok_200, redirect, not_found, errors, other = analyze("API sample", api)

# Detailed API status breakdown
statuses = {}
for r in api:
    s = r.get('direct_status', r.get('final_status', 0))
    statuses[s] = statuses.get(s, 0) + 1

print(f'\nAPI status breakdown:')
for s in sorted(statuses.keys()):
    print(f'  {s}: {statuses[s]}')
