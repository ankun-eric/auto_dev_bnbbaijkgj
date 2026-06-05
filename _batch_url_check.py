import subprocess, json, time
BASE = 'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'

urls = [
    ('PAGE','/'),('PAGE','/login'),('PAGE','/ai-home'),('PAGE','/health-profile'),
    ('PAGE','/family'),('PAGE','/care-ai-home'),('PAGE','/tcm'),('PAGE','/points'),
    ('PAGE','/settings'),('PAGE','/scan'),('PAGE','/articles'),('PAGE','/news'),
    ('PAGE','/services'),('PAGE','/products'),('PAGE','/medical-records'),
    ('PAGE','/health-dashboard'),('PAGE','/member-center'),('PAGE','/merchant/login'),
    ('PAGE','/devices'),('PAGE','/glucose'),('PAGE','/invite'),('PAGE','/landing'),
    ('PAGE','/my-coupons'),('PAGE','/my-favorites'),('PAGE','/my-addresses'),
    ('PAGE','/chat-history'),('PAGE','/coupon-center'),('PAGE','/health-plan'),
    ('PAGE','/health-reminders'),('PAGE','/checkout'),('PAGE','/report-history'),
    ('PAGE','/cards'),('PAGE','/cards/wallet'),('PAGE','/points/mall'),
    ('PAGE','/points/exchange-records'),('PAGE','/legal/privacy-policy'),
    ('PAGE','/legal/service-agreement'),('PAGE','/welcome-mode'),
    ('PAGE','/health-metric/blood_pressure'),
    ('PAGE','/ai-home/medication-plans'),('PAGE','/ai-home/medication-plans/new'),
    ('PAGE','/health-plan/custom'),('PAGE','/health-plan/custom/create'),
    ('PAGE','/admin/login'),('PAGE','/admin/dashboard'),('PAGE','/admin/users'),
    ('PAGE','/admin/settings'),('PAGE','/admin/ai-config'),('PAGE','/admin/knowledge'),
    ('PAGE','/admin/points/mall'),('PAGE','/admin/points/levels'),
    ('PAGE','/admin/product-system/products'),('PAGE','/admin/product-system/orders'),
    ('PAGE','/admin/product-system/coupons'),('PAGE','/admin/merchant/accounts'),
    ('PAGE','/admin/content/articles'),('PAGE','/admin/health-plan/categories'),
    ('PAGE','/admin/health-plan/recommended'),
    ('API','/api/health'),('API','/api/system/server-time'),
    ('API','/api/ai-home-config'),('API','/api/h5/bottom-nav'),
    ('API','/api/app-settings/page-style'),('API','/api/config/login_ui_version'),
    ('API','/api/cities/list'),('API','/api/cities/hot'),
    ('API','/api/tcm/questions'),('API','/api/content/articles'),
    ('API','/api/home-config'),('API','/api/home-banners'),('API','/api/home-menus'),
    ('API','/api/landing'),('API','/api/h5/active-theme'),
    ('API','/api/products/categories'),('API','/api/products/hot-recommendations'),
    ('API','/api/coupons/available'),('API','/api/notices/active'),
    ('API','/api/settings/logo'),('API','/api/search/hot'),
    ('API','/api/services/categories'),('API','/api/services/items'),
    ('API','/api/common/time-slots'),('API','/api/points/level'),
    ('API','/api/relation-types'),('API','/api/merchant-categories'),
    ('API','/api/membership/plans'),('API','/api/chat/function-buttons'),
    ('API','/api/questionnaire/templates'),('API','/api/disease-presets'),
    ('API','/api/health-alerts'),('API','/api/health-archive-v5/overview'),
    ('API','/api/notifications/unread-count'),('API','/api/v2/regions'),
    ('API','/api/v5/system-config/doctor-consult'),
    ('API','/api/h5/checkout/init'),('API','/api/maps/geo-config'),
    ('API','/api/maps/static-map'),('API','/api/verify/checkin-records'),
    ('API','/api/v2/app/version-check'),('API','/api/public/protocol/privacy'),
    ('API','/api/user/mode-preference'),
]

results=[]
total=len(urls)
ok_count=0
loop_count=0
err4_count=0
err5_count=0

for i,(typ,path) in enumerate(urls):
    url=BASE+path
    try:
        r=subprocess.run([
            'curl.exe','-ILs','--connect-timeout','5','--max-time','15',
            '--max-redirs','15','-o','NUL',
            '-w','FINAL:%{http_code}|REDIRS:%{num_redirects}|URL:%{url_effective}|TIME:%{time_total}',
            url
        ],capture_output=True,text=True,timeout=20)
        out=r.stdout.strip()
        parts={}
        for part in out.split('|'):
            if ':' in part:
                k,v=part.split(':',1)
                parts[k]=v
        fc=parts.get('FINAL','000')
        rd=int(parts.get('REDIRS','0'))
        fu=parts.get('URL',url)
        tt=parts.get('TIME','0')
        loop=rd>=10
        reachable=fc in ['200','201','204','301','302','303','307','308','401','403','405','422']
        if reachable:ok_count+=1
        if loop:loop_count+=1
        if fc.startswith('4') and fc not in ['401','403','405','422']:err4_count+=1
        if fc.startswith('5'):err5_count+=1
        results.append({'type':typ,'path':path,'code':fc,'redirs':rd,'ok':reachable,'loop':loop,'time':tt})
        st='OK' if reachable else('LOOP' if loop else'FAIL')
        print(f'[{i+1:3d}/{total}] {st:4s} {fc:4s} R={rd:2d} {typ:4s} {path}')
    except Exception as e:
        results.append({'type':typ,'path':path,'code':'ERR','redirs':0,'ok':False,'loop':False,'err':str(e)[:80]})
        print(f'[{i+1:3d}/{total}] ERR        {typ:4s} {path}')

print(f'\n=== RESULTS ===')
print(f'Total: {total}')
print(f'Reachable: {ok_count} ({100*ok_count/total:.1f}%)')
print(f'Unreachable: {total-ok_count}')
print(f'  Redirect loops: {loop_count}')
print(f'  Real 4xx (excl auth/validation): {err4_count}')
print(f'  5xx: {err5_count}')

with open(r'C:\auto_output\bnbbaijkgj\_batch_check_results.json','w') as f:
    json.dump({'total':total,'reachable':ok_count,'unreachable':total-ok_count,'loops':loop_count,'results':results},f,indent=2)
print('Saved to _batch_check_results.json')
