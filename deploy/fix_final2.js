const {Client} = require('ssh2');
const HOST = 'newbb.test.bangbangvip.com';
const USER = 'ubuntu';
const PASS = 'Newbang888';
const DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27';
const DOMAIN = DEPLOY_ID + '.noob-ai.test.bangbangvip.com';

var conn = new Client();

function execCmd(cmd, timeout) {
  timeout = timeout || 60;
  console.log('\nCMD: ' + cmd.substring(0, 150));
  return new Promise(function(resolve, reject) {
    var timer = setTimeout(function() { reject(new Error('timeout')); }, timeout * 1000);
    conn.exec(cmd, function(err, stream) {
      if (err) { clearTimeout(timer); reject(err); return; }
      var out = '', errOut = '';
      stream.on('data', function(d) { var s = d.toString(); out += s; if (out.length < 3000) process.stdout.write(s); });
      stream.stderr.on('data', function(d) { errOut += d.toString(); });
      stream.on('close', function() {
        clearTimeout(timer);
        if (out.length > 3000) console.log('  ...(' + out.length + ' bytes)');
        if (errOut) console.log('  STDERR: ' + errOut.substring(0, 300));
        resolve({out: out.trim(), err: errOut.trim()});
      });
    });
  });
}

function sleep(ms) { return new Promise(function(r) { setTimeout(r, ms); }); }

async function main() {
  await new Promise(function(res, rej) {
    conn.on('ready', res);
    conn.on('error', rej);
    conn.connect({host: HOST, port: 22, username: USER, password: PASS, readyTimeout: 15000});
  });
  console.log('CONNECTED');

  // FIX 1: Check backend Python path
  console.log('\n=== FIX 1: Check Backend Python Path ===');
  var r = await execCmd('docker exec ' + DEPLOY_ID + '-backend python -c "import sys; print(sys.path)" 2>&1', 10);
  console.log('sys.path: ' + r.out);
  r = await execCmd('docker exec ' + DEPLOY_ID + '-backend ls /app/ 2>&1', 10);
  console.log('/app/: ' + r.out);
  r = await execCmd('docker exec ' + DEPLOY_ID + '-backend ls /app/app/ 2>&1', 10);
  console.log('/app/app/: ' + r.out);
  r = await execCmd('docker exec ' + DEPLOY_ID + '-backend find /app -name "database.py" -type f 2>/dev/null', 10);
  console.log('database.py: ' + r.out);

  // Run DB check using python from within /app
  r = await execCmd('docker exec -w /app ' + DEPLOY_ID + '-backend python -c "from app.database import engine; from sqlalchemy import inspect; i=inspect(engine); t=i.get_table_names(); print(len(t),tables); print(sorted(t)[:10])" 2>&1', 15);
  console.log('DB check: ' + r.out);

  // FIX 2: Fix admin healthcheck - change localhost to 127.0.0.1
  console.log('\n=== FIX 2: Fix Admin Healthcheck ===');
  // Read current healthcheck
  r = await execCmd('cd /home/ubuntu/' + DEPLOY_ID + ' && grep -A2 "admin-web:" docker-compose.prod.yml | grep "test:"');
  console.log('Current admin healthcheck: ' + r.out);

  // Fix: replace localhost with 127.0.0.1 in admin healthcheck
  r = await execCmd('cd /home/ubuntu/' + DEPLOY_ID + ' && sed -i "/admin-web:/,/h5-web:/ s|localhost:3000/admin|127.0.0.1:3000/admin/|g" docker-compose.prod.yml && echo DONE');
  console.log('Fix 127.0.0.1: ' + r.out);
  r = await execCmd('cd /home/ubuntu/' + DEPLOY_ID + ' && sed -i "/admin-web:/,/h5-web:/ s|127.0.0.1:3000/admin 2|127.0.0.1:3000/admin/ 2|g" docker-compose.prod.yml && echo DONE2');
  console.log('Fix wget: ' + r.out);

  // Verify fix
  r = await execCmd('cd /home/ubuntu/' + DEPLOY_ID + ' && grep -A2 "admin-web:" docker-compose.prod.yml | grep "test:"');
  console.log('Updated admin healthcheck: ' + r.out);

  // Recreate admin container
  r = await execCmd('cd /home/ubuntu/' + DEPLOY_ID + ' && docker compose -f docker-compose.prod.yml up -d --force-recreate admin-web 2>&1', 120);
  console.log('Recreate: ' + r.out.substring(Math.max(0, r.out.length - 300)));

  // Wait for health
  console.log('\nWaiting for admin healthy...');
  for (var i = 0; i < 18; i++) {
    await sleep(10000);
    r = await execCmd('docker ps --filter name=' + DEPLOY_ID + '-admin --format "{{.Status}}"', 5);
    console.log('[' + i + '] ' + r.out);
    if (r.out.toLowerCase().indexOf('healthy') >= 0) break;
  }

  // Final
  console.log('\n=== FINAL STATUS ===');
  r = await execCmd('docker ps --filter name=' + DEPLOY_ID + ' --format "table {{.Names}}\t{{.Status}}"');
  console.log(r.out);

  console.log('\n=== DEPLOYMENT COMPLETED ===');
  console.log('DEPLOY_ID:', DEPLOY_ID);
  console.log('URL: https://' + DOMAIN);
  console.log('Admin: https://' + DOMAIN + '/admin');
  console.log('H5: https://' + DOMAIN);
  console.log('API: https://' + DOMAIN + '/api/health');
  console.log('Account: admin / admin123');

  conn.end();
}
main().catch(function(e) { console.error('FATAL: ' + e.message); process.exit(1); });
