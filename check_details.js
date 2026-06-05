process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
const base = 'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com';
const admin = base + '/admin';

(async () => {
    const checks = [
        [admin + '/devices/catalog', 'Admin Device Catalog'],
        [admin + '/devices/scene-groups', 'Admin Device Scene Groups'],
        [admin + '/login', 'Admin Login'],
        [base + '/family/', 'Family Page'],
        [base + '/family-invite/', 'Family Invite'],
        [base + '/devices/', 'H5 Devices'],
        [base + '/health-profile/', 'Health Profile'],
        [base + '/api/docs', 'API Docs'],
        [base + '/api/openapi.json', 'OpenAPI JSON'],
    ];
    
    for (const [url, desc] of checks) {
        try {
            const r = await fetch(url, { redirect: 'manual' });
            let body = '';
            if (r.status === 200) {
                const t = await r.text();
                body = t.substring(0, 500);
            }
            const location = r.headers.get('location') || '';
            console.log(`[${r.status}] ${desc}: ${url} ${location ? '-> ' + location : ''}`);
            if (r.status === 200) {
                const titleMatch = body.match(/<title>([^<]+)<\/title>/);
                if (titleMatch) console.log('  Title:', titleMatch[1]);
            }
        } catch (e) {
            console.log(`[ERR] ${desc}: ${url} - ${e.message}`);
        }
    }
})();
