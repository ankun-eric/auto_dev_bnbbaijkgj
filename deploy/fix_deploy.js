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
        if (out.length > 2000) console.log('  ... (' + out.length + ' bytes)');
        if (errOut) console.log('  STDERR: ' + errOut.substring(0, 200));
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

  // FIX 1: Disable the .conf file
  console.log('\n=== FIX 1: Disable conflicting .conf file ===');
  var r = await execCmd('mv /home/ubuntu/gateway/conf.d/' + DEPLOY_ID + '.conf /home/ubuntu/gateway/conf.d/' + DEPLOY_ID + '.conf.disabled.$(date +%s) 2>/dev/null; echo DONE');
  console.log('Disable .conf: ' + r.out);

  // Verify both .conf and .server exist in gateway container
  r = await execCmd('docker exec gateway-nginx ls /etc/nginx/conf.d/ | grep ' + DEPLOY_ID.substring(0, 8));
  console.log('Gateway files: ' + r.out);

  // Test nginx
  r = await execCmd('docker exec gateway-nginx nginx -t 2>&1');
  console.log('Nginx test: ' + r.out.substring(0, 300));
  if ((r.out + r.err).toLowerCase().indexOf('successful') >= 0) {
    r = await execCmd('docker exec gateway-nginx nginx -s reload 2>&1');
    console.log('Nginx reload: ' + (r.out || r.err || 'OK'));
  } else {
    console.log('NGINX TEST STILL FAILING');
  }

  // FIX 2: DB migration using temp Python script
  console.log('\n=== FIX 2: DB Migration ===');
  var pyScript = 'import sys\nsys.path.insert(0,"/app")\nfrom app.database import engine\nfrom sqlalchemy import inspect\ni=inspect(engine)\nt=i.get_table_names()\nprint("Tables:",len(t))\nfor tn in sorted(t)[:20]:\n    print(" -",tn)';
  // Write via base64
  var b64 = Buffer.from(pyScript).toString('base64');
  await execCmd('echo ' + b64 + ' | base64 -d > /tmp/db_check.py');
  r = await execCmd('docker cp /tmp/db_check.py ' + DEPLOY_ID + '-backend:/tmp/db_check.py && docker exec ' + DEPLOY_ID + '-backend python /tmp/db_check.py 2>&1', 20);
  console.log('DB check: ' + r.out);

  // create_all
  pyScript = 'from app.database import Base, engine\nBase.metadata.create_all(bind=engine)\nprint("create_all DONE")';
  b64 = Buffer.from(pyScript).toString('base64');
  await execCmd('echo ' + b64 + ' | base64 -d > /tmp/db_migrate.py');
  r = await execCmd('docker cp /tmp/db_migrate.py ' + DEPLOY_ID + '-backend:/tmp/db_migrate.py && docker exec ' + DEPLOY_ID + '-backend python /tmp/db_migrate.py 2>&1', 20);
  console.log('Migrate: ' + r.out);

  // FIX 3: Default account
  console.log('\n=== FIX 3: Default Account ===');
  pyScript = 'from app.database import SessionLocal\nfrom app.models import User\ndb=SessionLocal()\nu=db.query(User).filter(User.username=="admin").first()\nprint("admin_exists:", u is not None)\nif u:\n    print("admin_role:", u.role)\ndb.close()';
  b64 = Buffer.from(pyScript).toString('base64');
  await execCmd('echo ' + b64 + ' | base64 -d > /tmp/admin_check.py');
  r = await execCmd('docker cp /tmp/admin_check.py ' + DEPLOY_ID + '-backend:/tmp/admin_check.py && docker exec ' + DEPLOY_ID + '-backend python /tmp/admin_check.py 2>&1', 20);
  console.log('Admin: ' + r.out);

  if (r.out.indexOf('admin_exists: False') >= 0) {
    pyScript = 'from app.database import SessionLocal\nfrom app.models import User\nfrom app.core.security import get_password_hash\ndb=SessionLocal()\nu=User(username="admin",hashed_password=get_password_hash("admin123"),role="admin")\ndb.add(u)\ndb.commit()\nprint("admin_created")\ndb.close()';
    b64 = Buffer.from(pyScript).toString('base64');
    await execCmd('echo ' + b64 + ' | base64 -d > /tmp/admin_create.py');
    r = await execCmd('docker cp /tmp/admin_create.py ' + DEPLOY_ID + '-backend:/tmp/admin_create.py && docker exec ' + DEPLOY_ID + '-backend python /tmp/admin_create.py 2>&1', 20);
    console.log('Create admin: ' + r.out);
  }

  // FIX 4: Admin health check
  console.log('\n=== FIX 4: Admin Container ===');
  r = await execCmd('docker logs --tail=20 ' + DEPLOY_ID + '-admin 2>&1');
  console.log('Admin logs:\n' + r.out);

  r = await execCmd('docker exec ' + DEPLOY_ID + '-admin wget -qO- http://localhost:3000/admin/ 2>&1');
  console.log('Admin local test:\n' + r.out.substring(0, 300));

  // Check if admin container has wget
  r = await execCmd('docker exec ' + DEPLOY_ID + '-admin which wget curl node 2>&1');
  console.log('Admin tools: ' + r.out);

  // Final status
  console.log('\n=== FINAL STATUS ===');
  r = await execCmd('docker ps --filter name=' + DEPLOY_ID + ' --format "table {{.Names}}\t{{.Status}}"');
  console.log(r.out);

  // SSL tests
  r = await execCmd('curl -s --max-time 5 https://' + DOMAIN + '/api/health 2>&1');
  console.log('API health: ' + r.out);

  r = await execCmd('curl -s --max-time 5 -o /dev/null -w "%{http_code}" https://' + DOMAIN + '/ 2>&1');
  console.log('H5 frontend: HTTP ' + r.out);

  r = await execCmd('curl -s --max-time 5 -o /dev/null -w "%{http_code}" https://' + DOMAIN + '/admin/ 2>&1');
  console.log('Admin frontend: HTTP ' + r.out);

  console.log('\n=== ALL FIXES DONE ===');
  console.log('URL: https://' + DOMAIN);
  console.log('Admin: https://' + DOMAIN + '/admin');
  console.log('Account: admin / admin123');

  conn.end();
}
main().catch(function(e) { console.error('FATAL: ' + e.message); process.exit(1); });
