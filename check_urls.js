const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com';
const ADMIN_BASE = BASE_URL + '/admin';
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
            headers: {
                'User-Agent': 'NoobTestSkill/1.0',
                ...headers,
            },
            rejectUnauthorized: false, // Allow self-signed certs
            timeout: TIMEOUT,
        };

        const req = client.request(options, (res) => {
            let body = '';
            res.on('data', (chunk) => { body += chunk; });
            res.on('end', () => {
                const elapsed = Date.now() - start;
                let bodyPreview = '';
                try {
                    const j = JSON.parse(body);
                    bodyPreview = JSON.stringify(j).substring(0, 300);
                } catch {
                    bodyPreview = body.substring(0, 300);
                }
                resolve({
                    url,
                    method,
                    status: res.statusCode,
                    elapsed,
                    bodyPreview,
                    ok: res.statusCode >= 200 && res.statusCode < 500,
                });
            });
        });

        req.on('error', (err) => {
            resolve({
                url,
                method,
                status: 0,
                elapsed: Date.now() - start,
                error: err.code || err.message,
                ok: false,
            });
        });

        req.on('timeout', () => {
            req.destroy();
            resolve({
                url,
                method,
                status: 0,
                elapsed: TIMEOUT,
                error: 'TIMEOUT',
                ok: false,
            });
        });

        req.end();
    });
}

async function runChecks() {
    const results = [];
    
    // ── 1. Critical URLs (specified in test requirements) ──
    const criticalUrls = [
        { url: BASE_URL + '/', desc: 'HTTPS Root' },
        { url: BASE_URL + '/api/health', desc: 'API Health Check' },
        { url: ADMIN_BASE + '/', desc: 'Admin Root' },
        { url: BASE_URL + '/family', desc: '/family page (should be 404)' },
        { url: BASE_URL + '/api/devices/scene-groups', desc: 'Device Scene Groups API' },
        { url: BASE_URL + '/api/family/accept-invitation', desc: 'F1: Family Accept Invitation (need POST)' },
        { url: BASE_URL + '/api/family/member', desc: 'F2: Family Member APIs' },
        { url: BASE_URL + '/api/family/members', desc: 'Family Members List' },
        { url: BASE_URL + '/api/family/invitation', desc: 'F3: Family Invitation API' },
        { url: BASE_URL + '/api/reverse-guardian/remove/send-code', desc: 'F12: Reverse Guardian Remove Send Code' },
        { url: BASE_URL + '/api/family/member/1/unbind/send-code', desc: 'F12: Family Member Unbind Send Code' },
        { url: BASE_URL + '/api/devices/catalog', desc: 'F8-F9: Device Catalog' },
        { url: BASE_URL + '/api/devices/my', desc: 'F8-F9: My Devices' },
        { url: BASE_URL + '/api/reverse-guardian/my-guardians', desc: 'Reverse Guardian List' },
        { url: BASE_URL + '/api/reverse-guardian/guardian-count', desc: 'Guardian Count' },
    ];

    console.log('=== Checking Critical URLs ===');
    for (const item of criticalUrls) {
        const r = await checkUrl(item.url);
        results.push({ ...r, desc: item.desc, category: 'critical' });
        const icon = r.ok ? (r.status === 404 ? '⚠️404' : '✅') : '❌';
        console.log(`${icon} [${r.status}] ${item.desc} (${r.elapsed}ms) - ${r.url}`);
    }

    // ── 2. Backend API routes (sample - check unique paths) ──
    console.log('\n=== Checking Backend API Routes (sample) ===');
    const raw = fs.readFileSync(path.join(__dirname, 'all_routes_extracted.json'), 'utf-8');
    const data = JSON.parse(raw);
    
    // Extract unique API paths (GET only for simplicity)
    const apiPaths = data.backend
        .filter(r => r.startsWith('GET '))
        .map(r => r.substring(4))
        .filter(p => !p.includes('{') && !p.includes('[')) // Skip dynamic routes
        .filter(p => p.startsWith('/api/'))
        .slice(0, 60); // Check first 60 unique paths
    
    for (const p of apiPaths) {
        const r = await checkUrl(BASE_URL + p);
        results.push({ ...r, desc: p, category: 'api' });
        const icon = r.ok ? (r.status === 404 ? '⚠️404' : '✅') : '❌';
        if (r.status !== 200 && r.status !== 404) {
            console.log(`${icon} [${r.status}] ${p} (${r.elapsed}ms)`);
        }
    }

    // ── 3. H5 frontend pages (sample) ──
    console.log('\n=== Checking H5 Frontend Pages (sample) ===');
    const h5Sample = data.h5_pages
        .filter(p => !p.includes('[') && !p.includes(']'))
        .slice(0, 40);
    
    for (const p of h5Sample) {
        const r = await checkUrl(BASE_URL + p);
        results.push({ ...r, desc: p, category: 'h5' });
        const icon = r.ok ? (r.status === 404 ? '⚠️404' : '✅') : '❌';
        if (r.status !== 200 && r.status !== 404) {
            console.log(`${icon} [${r.status}] ${p} (${r.elapsed}ms)`);
        }
    }

    // ── 4. Admin frontend pages (sample) ──
    console.log('\n=== Checking Admin Frontend Pages (sample) ===');
    const adminSample = data.admin_pages
        .filter(p => !p.includes('[') && !p.includes(']'))
        .slice(0, 30);
    
    for (const p of adminSample) {
        const r = await checkUrl(ADMIN_BASE + p);
        results.push({ ...r, desc: p, category: 'admin' });
        const icon = r.ok ? (r.status === 404 ? '⚠️404' : '✅') : '❌';
        if (r.status !== 200 && r.status !== 404) {
            console.log(`${icon} [${r.status}] ${p} (${r.elapsed}ms)`);
        }
    }

    // ── Summary ──
    const byCategory = {};
    const byStatus = {};
    for (const r of results) {
        byCategory[r.category] = (byCategory[r.category] || 0) + 1;
        const key = r.status.toString();
        byStatus[key] = (byStatus[key] || 0) + 1;
    }

    const summary = {
        total_checked: results.length,
        by_category: byCategory,
        by_status: byStatus,
        errors: results.filter(r => !r.ok && r.status !== 404),
        not_found: results.filter(r => r.status === 404),
        results: results,
    };

    fs.writeFileSync(path.join(__dirname, 'url_check_results.json'), JSON.stringify(summary, null, 2));
    
    console.log('\n=== Summary ===');
    console.log('Total checked:', results.length);
    console.log('By status:', JSON.stringify(byStatus));
    console.log('Errors (non-404):', summary.errors.length);
    console.log('404s:', summary.not_found.length);
    console.log('Saved to url_check_results.json');
}

runChecks().catch(console.error);
