const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

const BASE = 'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com';
const ADMIN_BASE = BASE + '/admin';
const TIMEOUT = 15000;

function checkUrl(url, method = 'GET', headers = {}) {
    return new Promise((resolve) => {
        const start = Date.now();
        const urlObj = new URL(url);
        const client = urlObj.protocol === 'https:' ? https : http;
        const options = {
            hostname: urlObj.hostname,
            port: urlObj.port,
            path: urlObj.pathname + urlObj.search,
            method: method,
            headers: { 'User-Agent': 'NoobTestSkill/1.0', ...headers },
            rejectUnauthorized: false,
            timeout: TIMEOUT,
        };
        const req = client.request(options, (res) => {
            let body = '';
            res.on('data', (chunk) => { body += chunk; if (body.length > 500) res.destroy(); });
            res.on('end', () => {
                const elapsed = Date.now() - start;
                let bodyPreview = '';
                try { bodyPreview = JSON.stringify(JSON.parse(body)).substring(0, 200); }
                catch { bodyPreview = body.substring(0, 200).replace(/\n/g, ' ').replace(/\r/g, ''); }
                resolve({ url, method, status: res.statusCode, elapsed, bodyPreview,
                    ok: res.statusCode > 0 && res.statusCode !== 502 && res.statusCode !== 503 && res.statusCode !== 504
                });
            });
        });
        req.on('error', (err) => resolve({ url, method, status: 0, elapsed: Date.now() - start, error: err.code || err.message, ok: false }));
        req.on('timeout', () => { req.destroy(); resolve({ url, method, status: -1, elapsed: TIMEOUT, error: 'TIMEOUT', ok: false }); });
        req.end();
    });
}

async function run() {
    const results = [];
    const raw = fs.readFileSync(path.join(__dirname, 'all_routes_extracted.json'), 'utf-8');
    const data = JSON.parse(raw);

    // ── 1. Critical + Payment endpoints ──
    console.log('=== 1. Critical + Payment Endpoints ===');
    const critical = [
        { url: BASE + '/', desc: 'HTTPS Root', cat: 'critical' },
        { url: BASE + '/api/health', desc: 'API Health', cat: 'critical' },
        { url: ADMIN_BASE + '/', desc: 'Admin Root', cat: 'critical' },
        { url: BASE + '/api/openapi.json', desc: 'OpenAPI Schema', cat: 'critical' },
        { url: BASE + '/api/docs', desc: 'Swagger Docs', cat: 'critical' },
        { url: BASE + '/api/redoc', desc: 'ReDoc', cat: 'critical' },
        { url: BASE + '/api/system/server-time', desc: 'Server Time', cat: 'critical' },
        { url: BASE + '/api/v2/app/version-check', desc: 'App Version Check', cat: 'critical' },
        { url: BASE + '/api/config', desc: 'Config', cat: 'critical' },
        { url: BASE + '/api/landing', desc: 'Landing', cat: 'critical' },
        { url: BASE + '/api/public/protocol/privacy-policy', desc: 'Privacy Policy', cat: 'critical' },
        { url: BASE + '/api/public/protocol/service-agreement', desc: 'Service Agreement', cat: 'critical' },
        // Payment related
        { url: BASE + '/api/pay/available-methods?platform=h5', desc: 'Pay Methods H5', cat: 'payment' },
        { url: BASE + '/api/pay/available-methods?platform=miniprogram', desc: 'Pay Methods MiniProgram', cat: 'payment' },
        { url: BASE + '/api/admin/payment-channels/wechat_miniprogram', desc: 'WxPay Channel Config', cat: 'payment' },
        { url: BASE + '/api/admin/payment-channels/alipay_h5', desc: 'Alipay Channel Config', cat: 'payment' },
        { url: BASE + '/api/admin/payment-channels/wechat_miniprogram/default-notify-url', desc: 'WxPay Default Notify URL', cat: 'payment' },
        { url: BASE + '/api/admin/payment-channels/alipay_h5/default-notify-url', desc: 'Alipay Default Notify URL', cat: 'payment' },
        { url: BASE + '/api/admin/refunds', desc: 'Refund List', cat: 'payment' },
        { url: BASE + '/api/orders/unified/counts', desc: 'Order Counts', cat: 'payment' },
        { url: BASE + '/api/orders/unified/sandbox-confirm', desc: 'Sandbox Confirm', cat: 'payment' },
        { url: BASE + '/api/payment/alipay/notify', desc: 'Alipay Notify', cat: 'payment' },
    ];
    for (const c of critical) {
        const r = await checkUrl(c.url);
        results.push({ ...r, desc: c.desc, category: c.cat });
        const icon = r.ok ? (r.status === 404 ? '⚠️404' : r.status === 405 ? '⚠️405' : (r.status === 401 || r.status === 403) ? '🔒' + r.status : '✅') : '❌';
        console.log(icon + ' [' + r.status + '] ' + c.desc + ' (' + r.elapsed + 'ms)');
    }

    // ── 2. Backend API sample (unique GET endpoints, exclude dynamic paths) ──
    console.log('\n=== 2. Backend API Sample (GET endpoints) ===');
    const apiGetPaths = data.backend
        .filter(r => r.method === 'GET')
        .map(r => r.path)
        .filter(p => !p.includes('{') && !p.includes('['))
        .filter((p, i, a) => a.indexOf(p) === i)
        .slice(0, 150);

    let apiOk = 0, apiFail = 0, api404 = 0;
    for (const p of apiGetPaths) {
        const r = await checkUrl(BASE + p);
        results.push({ ...r, desc: p, category: 'api' });
        if (r.ok) apiOk++;
        else if (r.status === 404) api404++;
        else apiFail++;
        if (!r.ok || r.status === 404) {
            const icon = r.status === 404 ? '⚠️404' : '❌';
            console.log(icon + ' [' + r.status + '] GET ' + p + ' (' + r.elapsed + 'ms) ' + r.bodyPreview.slice(0, 80));
        }
    }
    console.log('API Results: OK=' + apiOk + ' 404=' + api404 + ' FAIL=' + apiFail);

    // ── 3. Backend API POST/RESTRICTED sample ──
    console.log('\n=== 3. Backend API (POST + restricted endpoints) ===');
    const restrictedPaths = data.backend
        .filter(r => r.method === 'POST')
        .map(r => r.path)
        .filter((p, i, a) => a.indexOf(p) === i)
        .slice(0, 80);

    let restOk = 0, restFail = 0, rest405 = 0;
    for (const p of restrictedPaths) {
        const r = await checkUrl(BASE + p);
        results.push({ ...r, desc: p, category: 'api' });
        if (r.ok || r.status === 405 || r.status === 422) restOk++;
        else restFail++;
        if (r.status === 502 || r.status === 503 || r.status === 0) {
            console.log('❌ [' + r.status + '] POST ' + p + ' (' + r.elapsed + 'ms)');
        }
        if (r.status === 405) rest405++;
    }
    console.log('POST Results: OK/405/422=' + restOk + ' FAIL=' + restFail + ' (405=' + rest405 + ')');

    // ── 4. H5 frontend pages ──
    console.log('\n=== 4. H5 Frontend Pages ===');
    let h5Ok = 0, h5Fail = 0, h5308 = 0;
    for (const p of data.h5_pages.slice(0, 120)) {
        if (p.includes('[')) continue;
        const r = await checkUrl(BASE + p);
        results.push({ ...r, desc: p, category: 'h5' });
        if (r.ok && r.status < 400) h5Ok++;
        else if (r.status === 308) h5308++;
        else h5Fail++;
        if (r.status !== 200 && r.status !== 308) {
            console.log('❌ [' + r.status + '] ' + p + ' (' + r.elapsed + 'ms)');
        }
    }
    console.log('H5 Results: 200=' + h5Ok + ' 308=' + h5308 + ' FAIL=' + h5Fail);

    // ── 5. Admin frontend pages ──
    console.log('\n=== 5. Admin Frontend Pages ===');
    let admOk = 0, admFail = 0, adm308 = 0;
    for (const p of data.admin_pages.slice(0, 100)) {
        if (p.includes('[')) continue;
        const r = await checkUrl(ADMIN_BASE + p);
        results.push({ ...r, desc: p, category: 'admin' });
        if (r.ok && r.status < 400) admOk++;
        else if (r.status === 308) adm308++;
        else admFail++;
        if (r.status !== 200 && r.status !== 308) {
            console.log('❌ [' + r.status + '] /admin' + p + ' (' + r.elapsed + 'ms)');
        }
    }
    console.log('Admin Results: 200=' + admOk + ' 308=' + adm308 + ' FAIL=' + admFail);

    // ── 6. Summary ──
    const byCat = {}, byStat = {};
    for (const r of results) {
        byCat[r.category] = (byCat[r.category] || 0) + 1;
        byStat[r.status] = (byStat[r.status] || 0) + 1;
    }
    const errors = results.filter(r => !r.ok && r.status !== 404 && r.status !== 405 && r.status !== 401 && r.status !== 403 && r.status !== 422);
    const notFound = results.filter(r => r.status === 404);

    const summary = {
        total_checked: results.length,
        by_category: byCat,
        by_status: byStat,
        reachable: results.filter(r => r.ok || r.status === 308).length,
        unreachable: errors.length,
        errors: errors,
        not_found: notFound,
        results: results,
    };
    fs.writeFileSync(path.join(__dirname, 'fresh_check_results.json'), JSON.stringify(summary, null, 2));

    console.log('\n═══════════════════════════════════════════');
    console.log('  FINAL SUMMARY');
    console.log('═══════════════════════════════════════════');
    console.log('Total checked:', summary.total_checked);
    console.log('Reachable (200/308):', summary.reachable);
    console.log('Auth-required (401/403):', (byStat['401'] || 0) + (byStat['403'] || 0));
    console.log('Method error (405):', byStat['405'] || 0);
    console.log('Unreachable (502/503/504/0):', summary.unreachable);
    console.log('404:', summary.not_found.length);
    console.log('By status:', JSON.stringify(byStat));
    console.log('Results saved to fresh_check_results.json');
}

run().catch(console.error);
