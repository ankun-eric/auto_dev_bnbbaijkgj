const { Client } = require('ssh2');
const https = require('https');

const SERVER = { host: 'newbb.test.bangbangvip.com', port: 22, username: 'ubuntu', password: 'Newbang888' };
const DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27';
const DOMAIN = '6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com';

// Execute migration via SSH
function runMigration() {
  return new Promise((resolve, reject) => {
    const conn = new Client();
    conn.on('ready', () => {
      console.log('执行数据库迁移...');
      const cmd = `docker exec ${DEPLOY_ID}-backend python -c "
from app.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SHOW COLUMNS FROM users LIKE \\\"is_active\\\"'))
    if result.rowcount == 0:
        conn.execute(text('ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE'))
        print('ADDED: is_active')
    else:
        print('EXISTS: is_active')
    result = conn.execute(text('SHOW COLUMNS FROM users LIKE \\\"deleted_at\\\"'))
    if result.rowcount == 0:
        conn.execute(text('ALTER TABLE users ADD COLUMN deleted_at DATETIME NULL DEFAULT NULL'))
        print('ADDED: deleted_at')
    else:
        print('EXISTS: deleted_at')
    conn.commit()
    print('数据库迁移完成')
"
`;
      conn.exec(cmd, (err, stream) => {
        if (err) { conn.end(); reject(err); return; }
        let output = '';
        stream.on('data', (d) => { output += d.toString(); });
        stream.stderr.on('data', (d) => { output += d.toString(); });
        stream.on('close', () => { conn.end(); resolve(output); });
      });
    });
    conn.on('error', (e) => reject(e));
    conn.connect(SERVER);
  });
}

// Check HTTPS endpoints
function checkEndpoint(url, method = 'GET') {
  return new Promise((resolve) => {
    const u = new URL(url);
    const options = {
      hostname: u.hostname, port: 443, path: u.pathname,
      method: method,
      headers: { 'Content-Type': 'application/json' },
      rejectUnauthorized: false,
      timeout: 15000
    };
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (d) => body += d);
      res.on('end', () => resolve({ url, method, status: res.statusCode, body: body.substring(0, 200) }));
    });
    req.on('error', (e) => resolve({ url, method, status: 0, error: e.message }));
    req.on('timeout', () => { req.destroy(); resolve({ url, method, status: 0, error: 'timeout' }); });
    if (method === 'POST') req.write('{"code":"123456"}');
    req.end();
  });
}

async function main() {
  // Step 1: Database migration
  try {
    const result = await runMigration();
    console.log('迁移结果:', result);
  } catch(e) {
    console.log('迁移失败:', e.message);
  }

  // Step 2: Test endpoints
  console.log('\n验证端点...');
  const results = await Promise.all([
    checkEndpoint(`https://${DOMAIN}/api/health`),
    checkEndpoint(`https://${DOMAIN}/api/user/deactivate`, 'POST'),
    checkEndpoint(`https://${DOMAIN}/api/family/member/state/list`),
    checkEndpoint(`https://${DOMAIN}/api/`),
  ]);
  results.forEach(r => {
    console.log(`${r.method} ${r.url} → ${r.status} ${r.body || r.error || ''}`);
  });
}

main().catch(console.error);
