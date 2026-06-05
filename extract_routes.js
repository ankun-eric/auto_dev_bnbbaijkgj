const fs = require('fs');
const path = require('path');
const BASE = 'C:/auto_output/bnbbaijkgj';

// ── Backend routes from raw file ──
const raw = fs.readFileSync(path.join(BASE, 'be_routes.txt'), 'utf-8');
const routes = new Set();

for (const line of raw.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const m = trimmed.match(/@\w+\.(get|post|put|delete|patch)\s*\(\s*["']([^"']+)['"]/i);
    if (m) {
        routes.add(m[1].toUpperCase() + ' ' + m[2]);
    }
}

// Add prefixed routes from specific files
function fileRoutes(fn, prefix) {
    try {
        const content = fs.readFileSync(path.join(BASE, 'backend/app/api', fn), 'utf-8');
        const rgx = /@\w+\.(get|post|put|delete|patch)\s*\(\s*["']([^"']+)['"]/gi;
        let m;
        while ((m = rgx.exec(content)) !== null) {
            let full = (prefix + m[2]).replace(/\/\//g, '/');
            if (!full.startsWith('/')) full = '/' + full;
            routes.add(m[1].toUpperCase() + ' ' + full);
        }
    } catch(e) {
        console.error('Error reading', fn, e.message);
    }
}

fileRoutes('devices_v2.py', '/api/devices');
fileRoutes('reverse_guardian.py', '/api/reverse-guardian');
fileRoutes('sms.py', '/api/admin/sms');
fileRoutes('family_management.py', '');
fileRoutes('family.py', '');

// main.py routes
try {
    const mainContent = fs.readFileSync(path.join(BASE, 'backend/app/main.py'), 'utf-8');
    const mainRgx = /@app\.(get|post|put|delete|patch)\s*\(\s*["']([^"']+)['"]/gi;
    let m;
    while ((m = mainRgx.exec(mainContent)) !== null) {
        routes.add(m[1].toUpperCase() + ' ' + m[2]);
    }
} catch(e) {}

routes.add('GET /api/health');

const beList = [...routes].sort();

// ── H5 and Admin pages: read from saved dir output ──
const h5Raw = fs.readFileSync(path.join(BASE, 'h5_pages_raw.txt'), 'utf-8');
const adminRaw = fs.readFileSync(path.join(BASE, 'admin_pages_raw.txt'), 'utf-8');

function computePages(rawText, appDir) {
    const pages = new Set();
    for (const line of rawText.split('\n')) {
        if (!line.trim()) continue;
        const d = path.dirname(line.trim());
        let rel = path.relative(appDir, d).replace(/\\/g, '/');
        let segs = rel.split('/').filter(s => s && !(s.startsWith('(') && s.endsWith(')')));
        let pp = '/' + segs.join('/');
        if (!pp || pp === '/') pp = '/';
        pp = pp.replace(/\/\//g, '/');
        pages.add(pp);
    }
    return [...pages].sort();
}

const h5Pages = computePages(h5Raw, path.join(BASE, 'h5-web/src/app'));
const adminPages = computePages(adminRaw, path.join(BASE, 'admin-web/src/app'));

const result = {
    backend: beList,
    h5_pages: h5Pages,
    admin_pages: adminPages,
    stats: {
        backend_routes: beList.length,
        h5_pages: h5Pages.length,
        admin_pages: adminPages.length,
    }
};

fs.writeFileSync(path.join(BASE, 'all_routes_extracted.json'), JSON.stringify(result, null, 2));
console.log('Backend routes:', beList.length);
console.log('H5 pages:', h5Pages.length);
console.log('Admin pages:', adminPages.length);
console.log('Saved to all_routes_extracted.json');
