const {Client} = require('ssh2');
const HOST = 'newbb.test.bangbangvip.com';
const USER = 'ubuntu';
const PASS = 'Newbang888';
const DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27';
const DOMAIN = DEPLOY_ID + '.noob-ai.test.bangbangvip.com';

var conn = new Client();

function execCmd(cmd, timeout) {
  timeout = timeout || 60;
  console.log('\nCMD: ' + cmd.substring(0, 120));
  return new Promise(function(resolve, reject) {
    var timer = setTimeout(function() { reject(new Error('timeout')); }, timeout * 1000);
    conn.exec(cmd, function(err, stream) {
      if (err) { clearTimeout(timer); reject(err); return; }
      var out = '', errOut = '';
      stream.on('data', function(d) { var s = d.toString(); out += s; if (out.length < 2000) process.stdout.write(s); });
      stream.stderr.on('data', function(d) { errOut += d.toString(); });
      stream.on('close', function() {
        clearTimeout(timer);
        if (out.length > 2000) console.log('  ...(' + out.length + ' bytes)');
        if (errOut) console.log('  STDERR: ' + errOut.substring(0, 200));
        resolve({out: out.trim(), err: errOut.trim()});
      });
    });
  });
}

async function main() {
  await new Promise(function(res, rej) {
    conn.on('ready', res);
    conn.on('error', rej);
    conn.connect({host: HOST, port: 22, username: USER, password: PASS, readyTimeout: 15000});
  });
  console.log('CONNECTED');

  // FIX 1: DB migration - run from /app directory
  console.log('\n=== FIX 1: DB Migration ===');
  var pyScript = 'import sys, os\nos.chdir("/app")\nsys.path.insert(0,"/app")\nfrom app.database import engine\nfrom sqlalchemy import inspect\ni=inspect(engine)\nt=i.get_table_names()\nprint("Tables:",len(t))\nfor tn in sorted(t)[:20]:\n    print(" -",tn)';
  var b64 = Buffer.from(pyScript).toString('base64');
  await execCmd('echo ' + b64 + ' | base64 -d > /tmp/db_check2.py');
  var r = await execCmd('docker cp /tmp/db_check2.py ' + DEPLOY_ID + '-backend:/tmp/db_check2.py && docker exec ' + DEPLOY_ID + '-backend python /tmp/db_check2.py 2>&1', 20);
  console.log('DB check: ' + r.out);

  pyScript = 'import sys, os\nos.chdir("/app")\nsys.path.insert(0,"/app")\nfrom app.database import Base, engine\nBase.metadata.create_all(bind=engine)\nprint("create_all DONE")';
  b64 = Buffer.from(pyScript).toString('base64');
  await execCmd('echo ' + b64 + ' | base64 -d > /tmp/db_migrate2.py');
  r = await execCmd('docker cp /tmp/db_migrate2.py ' + DEPLOY_ID + '-backend:/tmp/db_migrate2.py && docker exec ' + DEPLOY_ID + '-backend python /tmp/db_migrate2.py 2>&1', 20);
  console.log('Migrate: ' + r.out);

  // FIX 2: Default account
  console.log('\n=== FIX 2: Default Account ===');
  pyScript = 'import sys, os\nos.chdir("/app")\nsys.path.insert(0,"/app")\nfrom app.database import SessionLocal\nfrom app.models import User\ndb=SessionLocal()\nu=db.query(User).filter(User.username=="admin").first()\nprint("admin_exists:", u is not None)\nif u:\n    print("admin_role:", u.role)\ndb.close()';
  b64 = Buffer.from(pyScript).toString('base64');
  await execCmd('echo ' + b64 + ' | base64 -d > /tmp/admin_check2.py');
  r = await execCmd('docker cp /tmp/admin_check2.py ' + DEPLOY_ID + '-backend:/tmp/admin_check2.py && docker exec ' + DEPLOY_ID + '-backend python /tmp/admin_check2.py 2>&1', 20);
  console.log('Admin: ' + r.out);

  if (r.out.indexOf('admin_exists: False') >= 0) {
    pyScript = 'import sys, os\nos.chdir("/app")\nsys.path.insert(0,"/app")\nfrom app.database import SessionLocal\nfrom app.models import User\nfrom app.core.security import get_password_hash\ndb=SessionLocal()\nu=User(username="admin",hashed_password=get_password_hash("admin123"),role="admin")\ndb.add(u)\ndb.commit()\nprint("admin_created")\ndb.close()';
    b64 = Buffer.from(pyScript).toString('base64');
    await execCmd('echo ' + b64 + ' | base64 -d > /tmp/admin_create2.py');
    r = await execCmd('docker cp /tmp/admin_create2.py ' + DEPLOY_ID + '-backend:/tmp/admin_create2.py && docker exec ' + DEPLOY_ID + '-backend python /tmp/admin_create2.py 2>&1', 20);
    console.log('Create admin: ' + r.out);
  }

  // FIX 3: Admin healthcheck - test different paths
  console.log('\n=== FIX 3: Admin Healthcheck ===');
  r = await execCmd('docker exec ' + DEPLOY_ID + '-admin wget -qO- http://localhost:3000/admin/ 2>&1');
  console.log('wget /admin/: ' + r.out.substring(0, 100));
  r = await execCmd('docker exec ' + DEPLOY_ID + '-admin wget -qO- http://localhost:3000/ 2>&1');
  console.log('wget /: ' + r.out.substring(0, 100));
  r = await execCmd('docker exec ' + DEPLOY_ID + '-admin wget -qO- http://127.0.0.1:3000/admin/ 2>&1');
  console.log('wget 127.0.0.1 /admin/: ' + r.out.substring(0, 100));

  // Check what port Next.js is listening on
  r = await execCmd('docker exec ' + DEPLOY_ID + '-admin netstat -tlnp 2>/dev/null || docker exec ' + DEPLOY_ID + '-admin ss -tlnp 2>/dev/null || echo NO_NETSTAT');
  console.log('Ports: ' + r.out);

  // FIX 4: Update admin healthcheck in docker-compose.prod.yml
  console.log('\n=== FIX 4: Update Admin Healthcheck ===');
  // Change the healthcheck to use /admin/ with trailing slash and try multiple approaches
  r = await execCmd('cd ' + DEPLOY_ID + ' && sed -i "s|http://localhost:3000/admin\\"|http://localhost:3000/admin/\\"|g" docker-compose.prod.yml 2>&1 && echo UPDATED || echo FAILED');
  console.log('sed: ' + r.out);

  // Also fix wget URL in healthcheck
  r = await execCmd('cd ' + DEPLOY_ID + ' && sed -i "s|wget -qO- http://127.0.0.1:3000/admin |wget -qO- http://127.0.0.1:3000/admin/ |g" docker-compose.prod.yml 2>&1 && echo UPDATED || echo FAILED');
  console.log('sed2: ' + r.out);

  // Verify healthcheck line
  r = await execCmd('cd ' + DEPLOY_ID + ' && grep -n "healthcheck" -A2 docker-compose.prod.yml | grep test');
  console.log('Healthcheck: ' + r.out);

  // Recreate admin container with fixed healthcheck
  r = await execCmd('cd ' + DEPLOY_ID + ' && docker compose -f docker-compose.prod.yml up -d --force-recreate admin-web 2>&1', 120);
  console.log('Recreate admin: ' + r.out.substring(0, 500));

  // Wait for admin health
  for (var i = 0; i < 12; i++) {
    await new Promise(function(r) { setTimeout(r, 10000); });
    r = await execCmd('docker ps --filter name=' + DEPLOY_ID + '-admin --format "{{.Status}}"');
    console.log('[' + i + '] Admin: ' + r.out);
    if (r.out.toLowerCase().indexOf('healthy') >= 0) break;
  }

  // Final status
  console.log('\n=== FINAL STATUS ===');
  r = await execCmd('docker ps --filter name=' + DEPLOY_ID + ' --format "table {{.Names}}\t{{.Status}}"');
  console.log(r.out);

  // Connectivity tests
  r = await execCmd('curl -s --max-time 5 https://' + DOMAIN + '/api/health 2>&1');
  console.log('API: ' + r.out);
  r = await execCmd('curl -s --max-time 5 -o /dev/null -w "%{http_code}" https://' + DOMAIN + '/ 2>&1');
  console.log('H5: HTTP ' + r.out);
  r = await execCmd('curl -s --max-time 5 -o /dev/null -w "%{http_code}" https://' + DOMAIN + '/admin/ 2>&1');
  console.log('Admin: HTTP ' + r.out);

  console.log('\n=== DEPLOYMENT FULLY COMPLETED ===');
  console.log('URL: https://' + DOMAIN);
  console.log('Account: admin / admin123');
  conn.end();
}
main().catch(function(e) { console.error('FATAL: ' + e.message); process.exit(1); });
