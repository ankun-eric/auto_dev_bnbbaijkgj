const { Client } = require('ssh2');
const https = require('https');

const SERVER = { host: 'newbb.test.bangbangvip.com', port: 22, username: 'ubuntu', password: 'Newbang888' };
const DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27';
const DOMAIN = '6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com';

function runMigration() {
  return new Promise((resolve, reject) => {
    const conn = new Client();
    conn.on('ready', () => {
      console.log('执行数据库迁移...');
      const cmd = `docker exec ${DEPLOY_ID}-backend python -c "
from sqlalchemy import text, create_engine
import os
engine = create_engine(os.environ.get('DATABASE_URL', 'mysql+aiomysql://root:password@host:3306/db'))
with engine.connect() as conn:
    r = conn.execute(text(\\\"SHOW COLUMNS FROM users LIKE 'is_active'\\\"))
    if r.rowcount == 0:
        conn.execute(text('ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE'))
        print('ADDED: is_active')
    else:
        print('EXISTS: is_active')
    r2 = conn.execute(text(\\\"SHOW COLUMNS FROM users LIKE 'deleted_at'\\\"))
    if r2.rowcount == 0:
        conn.execute(text('ALTER TABLE users ADD COLUMN deleted_at DATETIME NULL DEFAULT NULL'))
        print('ADDED: deleted_at')
    else:
        print('EXISTS: deleted_at')
    conn.commit()
print('OK')
"
`;
      conn.exec(cmd, (err, stream) => {
        if (err) { conn.end(); reject(err); return; }
        let output = '';
        stream.on('data', (d) => output += d.toString());
        stream.stderr.on('data', (d) => output += d.toString());
        stream.on('close', () => { conn.end(); resolve(output); });
      });
    });
    conn.on('error', (e) => reject(e));
    conn.connect(SERVER);
  });
}

function checkEndpoint(url, method = 'GET', body = null) {
  return new Promise((resolve) => {
    const u = new URL(url);
    const options = {
      hostname: u.hostname, port: 443, path: u.pathname,
      method: method,
      headers: { 'Content-Type': 'application/json' },
      rejectUnauthorized: false, timeout: 15000
    };
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (d) => data += d);
      res.on('end', () => resolve({ url, method, status: res.statusCode, body: data.substring(0, 300) }));
    });
    req.on('error', (e) => resolve({ url, method, status: 0, error: e.message }));
    req.on('timeout', () => { req.destroy(); resolve({ url, method, status: 0, error: 'timeout' }); });
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

async function main() {
  try {
    const r = await runMigration();
    console.log('迁移:', r);
  } catch(e) { console.log('迁移失败:', e.message); }

  console.log('\n=== 最终验证 ===');
  const tests = await Promise.all([
    checkEndpoint(`https://${DOMAIN}/api/health`),
    checkEndpoint(`https://${DOMAIN}/api/user/deactivate`, 'POST', {code:'123456'}),
    checkEndpoint(`https://${DOMAIN}/`),
    checkEndpoint(`https://${DOMAIN}/admin/`),
  ]);
  tests.forEach(t => console.log(`${t.method} ${t.url} → ${t.status} » ${t.body||t.error||''}`));
}
main().catch(console.error);
