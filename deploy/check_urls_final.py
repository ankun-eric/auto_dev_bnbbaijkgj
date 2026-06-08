import urllib.request, ssl, sys

ctx = ssl.create_default_context()
urls = [
    ('H5首页', 'https://chat.benne-ai.com/'),
    ('H5登录', 'https://chat.benne-ai.com/login'),
    ('管理后台', 'https://chat.benne-ai.com/admin/'),
    ('管理登录', 'https://chat.benne-ai.com/admin/login'),
    ('API健康', 'https://chat.benne-ai.com/api/health'),
    ('AI首页', 'https://chat.benne-ai.com/ai-home'),
    ('关怀版', 'https://chat.benne-ai.com/care-ai-home'),
    ('健康档案', 'https://chat.benne-ai.com/health-profile'),
    ('会员中心', 'https://chat.benne-ai.com/member-center'),
    ('我的设备', 'https://chat.benne-ai.com/devices'),
    ('脑力游戏', 'https://chat.benne-ai.com/brain-game'),
    ('消息列表', 'https://chat.benne-ai.com/messages'),
    ('家庭认证', 'https://chat.benne-ai.com/family-auth'),
    ('健康仪表盘', 'https://chat.benne-ai.com/health-dashboard'),
    ('数字安全绳', 'https://chat.benne-ai.com/care-safety-rope'),
    ('健康指南', 'https://chat.benne-ai.com/health-guide'),
    ('扫码', 'https://chat.benne-ai.com/scan'),
    ('商城产品', 'https://chat.benne-ai.com/products'),
    ('我的地址', 'https://chat.benne-ai.com/my-addresses'),
    ('设置页面', 'https://chat.benne-ai.com/settings'),
]

results = []
for name, url in urls:
    try:
        req = urllib.request.Request(url, method='HEAD')
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        results.append((resp.status, name, url))
    except urllib.error.HTTPError as e:
        results.append((e.code, name, url))
    except Exception as e:
        results.append((0, name, url, str(e)))

with open('deploy/link_check_results.json', 'w') as f:
    import json
    json.dump(results, f)

print(f'检查完成，共 {len(results)} 个URL')
ok = sum(1 for r in results if r[0] == 200 or r[0] == 308)
print(f'可达: {ok}/{len(results)}')
for r in results:
    status = 'OK' if r[0] == 200 or r[0] == 308 else 'FAIL'
    if len(r) == 3:
        print(f'  [{r[0]}] {status:5s} {r[1]:12s} {r[2]}')
    else:
        print(f'  [ERR] {status:5s} {r[1]:12s} {r[2]} - {r[3]}')
