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

async function main() {
  await new Promise(function(res, rej) {
    conn.on('ready', res);
    conn.on('error', rej);
    conn.connect({host: HOST, port: 22, username: USER, password: PASS, readyTimeout: 15000});
  });
  console.log('CONNECTED');

  // FIX: DB check with correct import path (app.core.database)
  console.log('\n=== DB Check ===');
  var r = await execCmd('docker exec -w /app ' + DEPLOY_ID + '-backend python -c "from app.core.database import engine; from sqlalchemy import inspect; i=inspect(engine); t=i.get_table_names(); print(\"Tables:\",len(t)); [print(\" - \"+x) for x in sorted(t)[:30]]" 2>&1', 15);
  console.log('DB tables: ' + r.out);

  // create_all
  console.log('\n=== DB Migration (create_all) ===');
  r = await execCmd('docker exec -w /app ' + DEPLOY_ID + '-backend python -c "from app.core.database import Base, engine; Base.metadata.create_all(bind=engine); print(\"create_all DONE\")" 2>&1', 15);
  console.log('Migration: ' + r.out);

  // Default account
  console.log('\n=== Default Account ===');
  r = await execCmd('docker exec -w /app ' + DEPLOY_ID + '-backend python -c "from app.core.database import SessionLocal; from app.models import User; db=SessionLocal(); u=db.query(User).filter(User.username==\"admin\").first(); print(\"admin_exists:\", u is not None); db.close()" 2>&1', 15);
  console.log('Admin: ' + r.out);

  // Final verification
  console.log('\n=== Final Verification ===');
  r = await execCmd('docker ps --filter name=' + DEPLOY_ID + ' --format "table {{.Names}}\t{{.Status}}"');
  console.log(r.out);

  r = await execCmd('curl -s --max-time 5 https://' + DOMAIN + '/api/health 2>&1');
  console.log('API: ' + r.out);

  console.log('\n=== ALL DONE ===');
  conn.end();
}
main().catch(function(e) { console.error('FATAL: ' + e.message); process.exit(1); });
