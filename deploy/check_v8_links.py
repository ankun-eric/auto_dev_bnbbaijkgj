"""v8 内容管理功能链接可达性检查。"""
import sys, json
sys.path.insert(0, '.')
from ssh_helper import create_client, run_cmd

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
BASE_URL = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'

# 前端页面 + 后端公开 API
LINKS = [
    # H5 页面
    ('H5', '/'),
    ('H5', '/login'),
    ('H5', '/news'),
    ('H5', '/articles'),
    ('H5', '/my-favorites'),
    # Admin-web
    ('ADMIN', '/admin'),
    ('ADMIN', '/admin/login'),
    # 后端 API
    ('API', '/api/health'),
    ('API', '/api/content/articles?page=1&page_size=3'),
    ('API', '/api/content/article-categories'),
    ('API', '/api/content/news?page=1&page_size=5'),
    ('API', '/api/content/news/latest?limit=5'),
]

ssh = create_client()
results = []
fail = 0
for kind, path in LINKS:
    full = f'{BASE_URL}{path}'
    out, _, _ = run_cmd(
        ssh,
        f'curl -s -o /dev/null -w "%{{http_code}}" -L -A "Mozilla/5.0 LinkCheck" '
        f'--max-time 15 "{full}"',
        timeout=30,
    )
    code = (out.strip() or '000')
    ok = code.startswith('2') or code.startswith('3')
    if not ok:
        fail += 1
    tag = 'OK' if ok else 'FAIL'
    line = f'[{code}] {tag} [{kind}] {path}'
    print(line)
    results.append({'kind': kind, 'path': path, 'http_code': code, 'ok': ok})

ssh.close()
report = {'base_url': BASE_URL, 'total': len(LINKS), 'failed': fail, 'results': results}
with open('link_check_v8_content.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f'\nSummary: total={len(LINKS)} failed={fail}')
sys.exit(1 if fail else 0)
