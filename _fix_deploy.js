const { Client } = require('ssh2');
const fs = require('fs');
const path = require('path');

const conn = new Client();
const config = {
  host: 'newbb.test.bangbangvip.com',
  port: 22,
  username: 'ubuntu',
  password: 'Newbang888',
  readyTimeout: 10000
};

const DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27';
const PROJECT_DIR = `/home/ubuntu/${DEPLOY_ID}`;

function exec(cmd) {
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

  // 1. Fix reverse_guardian.py on server - add Query import
  console.log('=== Fixing reverse_guardian.py ===');
  let r = await exec(`sed -i 's/from fastapi import APIRouter, Body, Depends, HTTPException/from fastapi import APIRouter, Body, Depends, HTTPException, Query/' ${PROJECT_DIR}/backend/app/api/reverse_guardian.py`);
  console.log('Fix applied:', r.stderr || 'OK');

  // 2. Verify the fix
  r = await exec(`head -15 ${PROJECT_DIR}/backend/app/api/reverse_guardian.py`);
  console.log('Verification:', r.stdout.split('\n').slice(11,14).join('\n'));

  // 3. Rebuild and restart backend
  console.log('\n=== Rebuilding backend ===');
  r = await exec(`cd ${PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1`, 120000);
  console.log(r.stdout.slice(-500));
  if (r.stderr) console.log('STDERR:', r.stderr.slice(-200));

  // 4. Restart backend
  console.log('\n=== Restarting backend ===');
  r = await exec(`cd ${PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend 2>&1`);
  console.log(r.stdout);

  // 5. Wait and check
  console.log('\nWaiting 20s...');
  await new Promise(r => setTimeout(r, 20000));
  
  r = await exec("docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}'");
  console.log('Status:');
  console.log(r.stdout);

  // 6. Health check
  console.log('\n=== Health Check ===');
  r = await exec(`docker exec ${DEPLOY_ID}-backend python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read().decode())" 2>&1`);
  console.log('API health:', r.stdout || r.stderr);

  // 7. Rebuild H5 frontend (to remove /family)
  console.log('\n=== Rebuilding H5 frontend (to remove /family) ===');
  r = await exec(`cd ${PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --no-cache h5 2>&1`, 120000);
  console.log(r.stdout.slice(-300));
  
  r = await exec(`cd ${PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5 2>&1`);
  console.log(r.stdout);

  // Wait and check all containers
  console.log('\nWaiting 15s...');
  await new Promise(r => setTimeout(r, 15000));
  
  r = await exec("docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}'");
  console.log('Final container status:');
  console.log(r.stdout);

  conn.end();
  console.log('\nDone.');
}

main().catch(e => { console.error('Error:', e.message); conn.end(); });
