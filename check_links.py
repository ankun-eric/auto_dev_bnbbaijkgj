import subprocess, sys

base = 'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'

checks = [
    ('GET', '/', 'RootPage'),
    ('GET', '/login/', 'LoginPage'),
    ('GET', '/ai-home/', 'AIHomePage'),
    ('GET', '/brain-game/', 'BrainGamePage'),
    ('GET', '/brain-game.html', 'BrainGameHTML'),
    ('GET', '/health-profile/', 'HealthProfile'),
    ('GET', '/merchant/login/', 'MerchantLogin'),
    ('GET', '/member-center/', 'MemberCenter'),
    ('GET', '/settings/', 'Settings'),
    ('GET', '/glucose/', 'GlucosePage'),
    ('GET', '/tcm/', 'TCMPage'),
    ('GET', '/products/', 'ProductsPage'),
    ('GET', '/news/', 'NewsPage'),
    ('GET', '/health-dashboard/', 'HealthDashboard'),
    ('GET', '/medical-records/', 'MedicalRecords'),
    ('GET', '/api/health', 'HealthAPI'),
    ('GET', '/api/brain-game/regions', 'RegionsAPI'),
    ('GET', '/api/brain-game/regions/tree', 'RegionsTreeAPI'),
    ('POST', '/api/brain-game/regions/sync-seed', 'SyncSeedAPI'),
    ('POST', '/api/brain-game/regions/clean-duplicates', 'CleanDupsAPI'),
    ('GET', '/api/cities', 'CitiesAPI'),
    ('GET', '/api/content/articles', 'ArticlesAPI'),
    ('GET', '/api/system/time', 'SystemTimeAPI'),
    ('GET', '/api/knowledge', 'KnowledgeAPI'),
]

with open('link_check_results.txt', 'w', encoding='utf-8') as f:
    for method, path, name in checks:
        url = base + path
        if method == 'POST':
            cmd = [
                'curl', '-s', '-o', 'nul', '-w', '%{http_code}',
                '--connect-timeout', '5', '--max-time', '15',
                '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '-d', '{}',
                url
            ]
        else:
            cmd = [
                'curl', '-s', '-o', 'nul', '-w', '%{http_code}',
                '--connect-timeout', '5', '--max-time', '15',
                url
            ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            code = r.stdout.strip()
            line = f'{method} {path} -> {code}'
            print(line, flush=True)
            f.write(line + '\n')
        except Exception as e:
            line = f'{method} {path} -> ERROR: {e}'
            print(line, flush=True)
            f.write(line + '\n')

print('ALL DONE', flush=True)
