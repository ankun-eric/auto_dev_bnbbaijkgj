const { Client } = require('ssh2');
const conn = new Client();
const config = {
  host: 'newbb.test.bangbangvip.com',
  port: 22,
  username: 'ubuntu',
  password: 'Newbang888',
  readyTimeout: 10000
};
const DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27';
const PDIR = `/home/ubuntu/${DEPLOY_ID}`;

function exec(cmd, timeout = 60000) {
  return new Promise((resolve, reject) => {
    conn.exec(cmd, (err, stream) => {
      if (err) return reject(err);
      let o = '', e = '';
      stream.on('data', (d) => { o += d.toString(); });
      stream.stderr.on('data', (d) => { e += d.toString(); });
      stream.on('close', () => resolve({ stdout: o, stderr: e }));
    });
  });
}

async function main() {
  await new Promise((r, j) => { conn.on('ready', r); conn.on('error', j); conn.connect(config); });
  console.log('Connected!');

  // Check if /family source exists on server
  console.log('\n=== Check /family source ===');
  let r = await exec(`ls -la ${PDIR}/h5-web/src/app/family/ 2>&1`);
  console.log(r.stdout || r.stderr);

  // Delete family directory if it exists
  if (r.stdout.includes('page.tsx') || r.stdout.includes('page')) {
    console.log('Deleting /family directory on server...');
    r = await exec(`rm -rf ${PDIR}/h5-web/src/app/family/`);
    console.log('Deleted:', r.stderr || 'OK');
  } else {
    console.log('/family directory does not exist on server - but page still served from docker image');
  }

  // Rebuild h5-web with no cache
  console.log('\n=== Rebuild h5-web (no cache) ===');
  r = await exec(`cd ${PDIR} && docker compose -f docker-compose.prod.yml build --no-cache h5-web 2>&1`, 180000);
  console.log(r.stdout.slice(-500));
  if (r.stderr) console.log('STDERR:', r.stderr.slice(-200));

  // Restart h5-web
  console.log('\n=== Restart h5-web ===');
  r = await exec(`cd ${PDIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1`);
  console.log(r.stdout);

  // Wait
  console.log('\nWaiting 20s...');
  await new Promise(r => setTimeout(r, 20000));

  r = await exec("docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}'");
  console.log('\nFinal status:');
  console.log(r.stdout);

  // Test /family
  console.log('\n=== Test /family ===');
  r = await exec("curl -k -s -o /dev/null -w '%{http_code}' https://localhost/family -H 'Host: 6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'");
  console.log('/family HTTP status:', r.stdout);

  conn.end();
}
main().catch(e => { console.error('Error:', e.message); conn.end(); });
