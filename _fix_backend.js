const { Client } = require('ssh2');

const conn = new Client();
const config = {
  host: 'newbb.test.bangbangvip.com',
  port: 22,
  username: 'ubuntu',
  password: 'Newbang888',
  readyTimeout: 10000
};

function exec(cmd, timeout = 30000) {
  return new Promise((resolve, reject) => {
    conn.exec(cmd, (err, stream) => {
      if (err) return reject(err);
      let stdout = '', stderr = '';
      stream.on('data', (d) => { stdout += d.toString(); });
      stream.stderr.on('data', (d) => { stderr += d.toString(); });
      stream.on('close', () => resolve({ stdout, stderr }));
    });
  });
}

async function main() {
  console.log('Connecting to server...');
  await new Promise((resolve, reject) => {
    conn.on('ready', resolve);
    conn.on('error', reject);
    conn.connect(config);
  });
  console.log('Connected!\n');

  // 1. Check container status
  console.log('=== Container Status ===');
  let r = await exec("docker ps -a --filter name=6b099ed3 --format '{{.Names}} {{.Status}} {{.Ports}}'");
  console.log(r.stdout || '(no containers found)');

  // 2. Check backend logs
  console.log('\n=== Backend Logs (last 50 lines) ===');
  r = await exec("docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --tail 50 2>&1");
  console.log(r.stdout || r.stderr);

  // 3. Try to restart backend
  console.log('\n=== Attempting to restart backend ===');
  r = await exec("cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml up -d backend 2>&1");
  console.log(r.stdout);
  console.log(r.stderr);

  // 4. Wait and check again
  console.log('\nWaiting 15s for container to start...');
  await new Promise(r => setTimeout(r, 15000));
  
  r = await exec("docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}'");
  console.log('Status after restart:');
  console.log(r.stdout);

  // 5. Check backend health
  console.log('\n=== Backend Health Check ===');
  r = await exec("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/health 2>&1");
  console.log('Health check status:', r.stdout);

  // 6. Check gateway config for /family
  console.log('\n=== Gateway /family check ===');
  r = await exec("curl -s -o /dev/null -w '%{http_code}' -k https://localhost/family -H 'Host: 6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com' 2>&1");
  console.log('/family HTTP status:', r.stdout);

  conn.end();
  console.log('\nDone.');
}

main().catch(e => { console.error('Error:', e.message); conn.end(); });
