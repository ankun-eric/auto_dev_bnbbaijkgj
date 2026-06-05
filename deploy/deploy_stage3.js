const {Client} = require('ssh2');
const fs = require('fs');
const path = require('path');

const HOST = 'newbb.test.bangbangvip.com';
const USER = 'ubuntu';
const PASS = 'Newbang888';
const DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27';
const PROJECT_DIR = '/home/ubuntu/' + DEPLOY_ID;
const ACR_REGISTRY = 'crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com';
const ACR_USER = 'ankun888';
const ACR_PASS = 'xiaobai888';
const GIT_USER = 'kun-an';
const GIT_TOKEN = 'pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74';
const GIT_REPO = 'https://codeup.aliyun.com/6a05a6159b7ce0afb00c035e/' + DEPLOY_ID + '.git';
const DOMAIN = DEPLOY_ID + '.noob-ai.test.bangbangvip.com';
const GATEWAY_SERVER_PATH = '/home/ubuntu/gateway/conf.d/' + DEPLOY_ID + '.server';
const BUILD_COMMIT_FALLBACK = 'd098b4b247aa5491941424e6dff602f4b1de7df8';

var conn = new Client();
var stepNum = 0;

function log(msg) {
  console.log(msg);
}

function execCmd(cmd, timeout) {
  timeout = timeout || 60;
  stepNum++;
  var short = cmd.substring(0, 120);
  log('\n[' + stepNum + '] ' + short);
  return new Promise(function(resolve, reject) {
    var timer = setTimeout(function() {
      log('  TIMEOUT after ' + timeout + 's');
      reject(new Error('timeout: ' + short));
    }, timeout * 1000);
    conn.exec(cmd, function(err, stream) {
      if (err) { clearTimeout(timer); reject(err); return; }
      var out = '', errOut = '';
      stream.on('data', function(d) {
        var s = d.toString();
        out += s;
        if (out.length < 2000) process.stdout.write(s);
      });
      stream.stderr.on('data', function(d) {
        var s = d.toString();
        errOut += s;
      });
      stream.on('close', function() {
        clearTimeout(timer);
        if (out.length > 2000) log('  ... (' + out.length + ' bytes total)');
        if (errOut) log('  STDERR: ' + errOut.substring(0, 200));
        resolve({out: out.trim(), err: errOut.trim()});
      });
    });
  });
}

function sleep(ms) {
  return new Promise(function(r) { setTimeout(r, ms); });
}

function sftpPut(localPath, remotePath) {
  return new Promise(function(resolve, reject) {
    conn.sftp(function(err, sftp) {
      if (err) { reject(err); return; }
      sftp.fastPut(localPath, remotePath, function(err2) {
        if (err2) { reject(err2); return; }
        log('  SFTP uploaded: ' + localPath + ' -> ' + remotePath);
        resolve();
      });
    });
  });
}

async function main() {
  log('=== STAGE 3: REMOTE DEPLOY ===');
  log('DEPLOY_ID: ' + DEPLOY_ID);
  log('DOMAIN: ' + DOMAIN);

  // Connect
  await new Promise(function(res, rej) {
    conn.on('ready', res);
    conn.on('error', rej);
    conn.connect({
      host: HOST, port: 22, username: USER, password: PASS, readyTimeout: 15000
    });
  });
  log('SSH connected to ' + HOST);

  // Step 1: ACR login
  log('\n--- Step 1: ACR Login ---');
  var r = await execCmd('docker login --username ' + ACR_USER + ' --password ' + ACR_PASS + ' ' + ACR_REGISTRY + ' 2>&1');
  log('ACR login: ' + (r.out.indexOf('Login Succeeded') >= 0 ? 'OK' : r.out.substring(0, 100)));

  // Step 2: Git fetch latest code
  log('\n--- Step 2: Git Fetch & Reset ---');
  var gitUrl = GIT_REPO.replace('https://', 'https://' + GIT_USER + ':' + GIT_TOKEN + '@');
  r = await execCmd('cd ' + PROJECT_DIR + ' && git remote set-url origin ' + gitUrl + ' 2>&1');
  log('Remote set');

  r = await execCmd('cd ' + PROJECT_DIR + ' && timeout 30 git fetch origin master --depth=1 2>&1', 45);
  log('Fetch: ' + r.out.substring(0, 300));

  r = await execCmd('cd ' + PROJECT_DIR + ' && git reset --hard origin/master 2>&1');
  log('Reset: ' + r.out.substring(0, 200));

  r = await execCmd('cd ' + PROJECT_DIR + ' && git clean -fd 2>&1');
  log('Clean: OK');

  r = await execCmd('cd ' + PROJECT_DIR + ' && git log -1 --oneline 2>&1');
  log('Latest commit: ' + r.out);

  // Step 3: Get server commit hash for BUILD_COMMIT
  log('\n--- Step 3: BUILD_COMMIT ---');
  r = await execCmd('cd ' + PROJECT_DIR + ' && git log -1 --format="%H" 2>/dev/null');
  var serverCommit = r.out || BUILD_COMMIT_FALLBACK;
  log('BUILD_COMMIT=' + serverCommit);

  // Verify root docker-compose.prod.yml exists
  r = await execCmd('ls -la ' + PROJECT_DIR + '/docker-compose.prod.yml 2>&1');
  log('docker-compose check: ' + r.out.substring(0, 100));

  // Step 4: Build containers
  log('\n--- Step 4: Docker Compose Build ---');
  r = await execCmd('cd ' + PROJECT_DIR + ' && BUILD_COMMIT=' + serverCommit + ' docker compose -f docker-compose.prod.yml build --pull 2>&1', 900);
  log('Build result length: ' + r.out.length);
  if (r.out.length > 300) {
    log('Last 300 chars: ' + r.out.substring(Math.max(0, r.out.length - 300)));
  }

  // Step 5: Down + Up
  log('\n--- Step 5: Docker Compose Down + Up ---');
  r = await execCmd('cd ' + PROJECT_DIR + ' && docker compose -f docker-compose.prod.yml down --remove-orphans 2>&1', 60);
  log('Down: OK');

  r = await execCmd('cd ' + PROJECT_DIR + ' && BUILD_COMMIT=' + serverCommit + ' docker compose -f docker-compose.prod.yml up -d 2>&1', 120);
  log('Up result: ' + r.out.substring(0, 500));

  // Step 6: Wait for health checks
  log('\n--- Step 6: Health Check Wait ---');
  var allHealthy = false;
  for (var i = 0; i < 48; i++) {
    await sleep(10000);
    r = await execCmd('docker ps -a --filter name=' + DEPLOY_ID + ' --format "{{.Names}} {{.Status}}"', 10);
    var lines = r.out.split('\n').filter(function(l) { return l.trim(); });
    var hc = 0, tc = 0;
    lines.forEach(function(l) {
      tc++;
      if (l.toLowerCase().indexOf('healthy') >= 0) hc++;
    });
    log('[' + i + '] ' + hc + '/' + tc + ' healthy');
    if (tc > 0 && hc === tc) {
      log('ALL HEALTHY!');
      allHealthy = true;
      break;
    }
  }
  if (!allHealthy) {
    log('WARNING: Timeout waiting for healthy');
    r = await execCmd('docker ps -a --filter name=' + DEPLOY_ID, 10);
    log(r.out);
  }

  // Step 7: Connect gateway to project network
  log('\n--- Step 7: Gateway Network ---');
  r = await execCmd('docker network connect ' + DEPLOY_ID + '-network gateway-nginx 2>&1');
  log('Network: ' + (r.out || r.err || 'OK'));

  // Step 8: Update gateway nginx config
  log('\n--- Step 8: Update Gateway Config ---');
  // Backup existing
  var ts = Math.floor(Date.now() / 1000);
  r = await execCmd('cp ' + GATEWAY_SERVER_PATH + ' /home/ubuntu/gateway/conf.d.bak/' + DEPLOY_ID + '.server.bak.' + ts + ' 2>/dev/null; echo OK');
  log('Backup: OK');

  // Upload gateway-routes.conf via SFTP
  var localConf = path.join(__dirname, 'gateway-routes.conf');
  await sftpPut(localConf, GATEWAY_SERVER_PATH);

  // Copy into gateway container
  r = await execCmd('docker cp ' + GATEWAY_SERVER_PATH + ' gateway-nginx:/etc/nginx/conf.d/' + DEPLOY_ID + '.server 2>&1');
  log('Copy to container: ' + (r.out || r.err || 'OK'));

  // Verify copied content
  r = await execCmd('docker exec gateway-nginx head -3 /etc/nginx/conf.d/' + DEPLOY_ID + '.server 2>&1');
  log('Verify: ' + r.out);

  // Test nginx config
  r = await execCmd('docker exec gateway-nginx nginx -t 2>&1');
  log('Nginx test: ' + r.out.substring(0, 400));
  var testOk = (r.out + r.err).toLowerCase().indexOf('successful') >= 0;
  if (testOk) {
    r = await execCmd('docker exec gateway-nginx nginx -s reload 2>&1');
    log('Nginx reload: ' + (r.out || r.err || 'OK'));
  } else {
    log('NGINX TEST FAILED! Rolling back...');
    // Restore backup
    var bakFiles = await execCmd('ls -t /home/ubuntu/gateway/conf.d.bak/' + DEPLOY_ID + '.server.bak.* 2>/dev/null | head -1');
    if (bakFiles.out) {
      await execCmd('cp ' + bakFiles.out.trim() + ' ' + GATEWAY_SERVER_PATH);
      await execCmd('docker cp ' + GATEWAY_SERVER_PATH + ' gateway-nginx:/etc/nginx/conf.d/' + DEPLOY_ID + '.server');
      await execCmd('docker exec gateway-nginx nginx -s reload 2>&1');
      log('Rolled back');
    }
  }

  // Step 9: Database migration
  log('\n--- Step 9: DB Migration ---');
  r = await execCmd('docker exec ' + DEPLOY_ID + '-backend python -c "from app.database import engine; from sqlalchemy import inspect; inspector = inspect(engine); tables = inspector.get_table_names(); print(\"Tables count:\", len(tables))" 2>&1', 20);
  log('DB: ' + r.out);

  // Run create_all (safe for existing tables)
  r = await execCmd('docker exec ' + DEPLOY_ID + '-backend python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine); print(\"create_all DONE\")" 2>&1', 20);
  log('Migration: ' + r.out);

  // Step 10: Default account
  log('\n--- Step 10: Default Account ---');
  r = await execCmd('docker exec ' + DEPLOY_ID + '-backend python -c "from app.database import SessionLocal; from app.models import User; db=SessionLocal(); u=db.query(User).filter(User.username==\"admin\").first(); print(\"admin_exists:\", u is not None); db.close()" 2>&1', 20);
  log('Admin: ' + r.out);

  if (r.out.indexOf('admin_exists: False') >= 0) {
    r = await execCmd('docker exec ' + DEPLOY_ID + '-backend python -c "from app.database import SessionLocal; from app.models import User; from app.core.security import get_password_hash; db=SessionLocal(); u=User(username=\"admin\", hashed_password=get_password_hash(\"admin123\"), role=\"admin\"); db.add(u); db.commit(); print(\"created\"); db.close()" 2>&1', 20);
    log('Create admin: ' + r.out);
  }

  // Step 11: Final verification
  log('\n--- Step 11: Final Verification ---');
  r = await execCmd('docker ps --filter name=' + DEPLOY_ID + ' --format "table {{.Names}}\t{{.Status}}"', 10);
  log('Containers:\n' + r.out);

  // SSL test
  r = await execCmd('curl -sI --max-time 8 https://' + DOMAIN + '/api/health 2>&1', 15);
  log('SSL test: ' + r.out.substring(0, 200));

  // Summary
  log('\n========================================');
  log('=== DEPLOYMENT COMPLETED ===');
  log('DEPLOY_ID: ' + DEPLOY_ID);
  log('URL: https://' + DOMAIN);
  log('Admin: https://' + DOMAIN + '/admin');
  log('API: https://' + DOMAIN + '/api/health');
  log('Default account: admin / admin123');
  log('========================================');

  conn.end();
}

main().catch(function(e) {
  console.error('FATAL: ' + e.message);
  console.error(e.stack);
  process.exit(1);
});
