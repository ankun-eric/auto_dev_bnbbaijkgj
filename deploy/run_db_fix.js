const {Client} = require('ssh2');
const fs = require('fs');
const path = require('path');

const HOST = 'newbb.test.bangbangvip.com';
const USER = 'ubuntu';
const PASS = 'Newbang888';
const DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27';
const DOMAIN = DEPLOY_ID + '.noob-ai.test.bangbangvip.com';
const SCRIPTS_DIR = path.join(__dirname, 'db_scripts');

var conn = new Client();

function execCmd(cmd, timeout) {
  timeout = timeout || 60;
  console.log('\nCMD: ' + cmd.substring(0, 120));
  return new Promise(function(resolve, reject) {
    var timer = setTimeout(function() { reject(new Error('timeout')); }, timeout * 1000);
    conn.exec(cmd, function(err, stream) {
      if (err) { clearTimeout(timer); reject(err); return; }
      var out = '', errOut = '';
      stream.on('data', function(d) { var s = d.toString(); out += s; process.stdout.write(s); });
      stream.stderr.on('data', function(d) { errOut += d.toString(); });
      stream.on('close', function() {
        clearTimeout(timer);
        if (errOut) console.log('STDERR: ' + errOut.substring(0, 200));
        resolve({out: out.trim(), err: errOut.trim()});
      });
    });
  });
}

function uploadAndRun(localFile, remoteFile) {
  return new Promise(async function(resolve, reject) {
    try {
      var content = fs.readFileSync(localFile, 'utf8');
      var b64 = Buffer.from(content).toString('base64');
      console.log('\n--- Uploading ' + path.basename(localFile) + ' (' + content.length + ' bytes) ---');
      // Write to server temp
      await execCmd('echo ' + b64 + ' | base64 -d > ' + remoteFile);
      // Copy to container and run
      var r = await execCmd('docker cp ' + remoteFile + ' ' + DEPLOY_ID + '-backend:' + remoteFile + ' && docker exec ' + DEPLOY_ID + '-backend python ' + remoteFile + ' 2>&1', 20);
      resolve(r);
    } catch(e) {
      reject(e);
    }
  });
}

async function main() {
  await new Promise(function(res, rej) {
    conn.on('ready', res);
    conn.on('error', rej);
    conn.connect({host: HOST, port: 22, username: USER, password: PASS, readyTimeout: 15000});
  });
  console.log('CONNECTED');

  // 1. Check DB tables
  console.log('\n========== 1. DB Table Check ==========');
  await uploadAndRun(path.join(SCRIPTS_DIR, 'check_db.py'), '/tmp/db_check.py');

  // 2. Run migration (create_all)
  console.log('\n========== 2. DB Migration ==========');
  await uploadAndRun(path.join(SCRIPTS_DIR, 'migrate.py'), '/tmp/db_migrate.py');

  // 3. Check admin account
  console.log('\n========== 3. Admin Account ==========');
  await uploadAndRun(path.join(SCRIPTS_DIR, 'admin_check.py'), '/tmp/admin_check.py');

  // 4. Final status
  console.log('\n========== FINAL ==========');
  var r = await execCmd('docker ps --filter name=' + DEPLOY_ID + ' --format "table {{.Names}}\t{{.Status}}"');
  console.log(r.out);
  r = await execCmd('curl -s --max-time 5 https://' + DOMAIN + '/api/health 2>&1');
  console.log('API: ' + r.out);

  console.log('\nDEPLOYMENT COMPLETE');
  console.log('URL: https://' + DOMAIN);
  conn.end();
}
main().catch(function(e) { console.error('FATAL: ' + e.message); process.exit(1); });
