import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'C:\auto_output\bnbbaijkgj\link_check_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

results = data['results']
total = len(results)
rch = [r for r in results if r['reachable']]
urch = [r for r in results if not r['reachable']]

print(f"TOTAL={total} OK={len(rch)} FAIL={len(urch)}")

# Just count categories
from collections import Counter
cats = Counter()
for r in urch:
    path = r['path']
    if path.startswith('/api/admin/api/'):
        cats['dev:双/api/前缀'] += 1
    elif r['classification'] == 'UNKNOWN_0':
        cats['dep:超时'] += 1
    elif r['classification'] == '404':
        cats['dep:API-404'] += 1
    else:
        cats[f'other:{r["classification"]}'] += 1

for k, v in cats.most_common():
    print(f"  {k}: {v}")
