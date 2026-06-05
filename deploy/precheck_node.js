const {Client} = require('ssh2');
const conn = new Client();

function execCmd(cmd, timeout=25) {
  return new Promise((resolve, reject) => {
    conn.exec(cmd, (err, stream) => {
      if(err) { reject(err); return; }
      let out='', errOut='';
      stream.on('data', d => out += d.toString());
      stream.stderr.on('data', d => errOut += d.toString());
      stream.on('close', () => resolve(out.trim() || errOut.trim()));
      setTimeout(() => reject('timeout'), timeout*1000);
    });
  });
}

async function main() {
  await new Promise((res, rej) => {
    conn.on('ready', res);
    conn.on('error', rej);
    conn.connect({host:'newbb.test.bangbangvip.com', port:22, username:'ubuntu', password:'Newbang888', readyTimeout:15000});
  });
  console.log('CONNECTED');

  let r;

  // 1. Gateway nginx config
  console.log('\n=== [1/6] Gateway nginx config ===');
  r = await execCmd('cat /home/ubuntu/gateway/nginx.conf | grep -n "include.*6b099ed3\\|include.*conf.d"');
  console.log('include lines:\n' + r);

  // 2. Routing check
  console.log('\n=== [2/6] Routing check ===');
  r = await execCmd('ls /home/ubuntu/gateway/conf.d/ | grep 6b099ed3');
  console.log('Our project files:\n' + r);
  r = await execCmd('wc -l /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.server 2>/dev/null || echo NOT_FOUND');
  console.log('.server file lines: ' + r);

  // 3. ACR images
  console.log('\n=== [3/6] ACR images ===');
  r = await execCmd('docker manifest inspect crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/python:3.12-slim >/dev/null 2>&1 && echo FOUND_python_3.12-slim || echo MISS_python_3.12-slim', 45);
  console.log('python:3.12-slim: ' + r);
  r = await execCmd('docker manifest inspect crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/node:20-alpine >/dev/null 2>&1 && echo FOUND_node_20-alpine || echo MISS_node_20-alpine', 45);
  console.log('node:20-alpine: ' + r);

  // 4. Docker networks
  console.log('\n=== [4/6] Docker networks ===');
  r = await execCmd('docker ps -a --filter name=gateway-nginx --format "{{.Names}} {{.Status}}"');
  console.log('gateway-nginx: ' + r);
  r = await execCmd('docker inspect gateway-nginx --format "{{range .NetworkSettings.Networks}}{{.Name}} {{end}}"');
  console.log('gateway networks: ' + r);
  r = await execCmd('docker network ls --filter name=6b099ed3-7175-4a78-91f4-44570c84ed27-network --format "{{.Name}}"');
  console.log('project network: ' + r);
  r = await execCmd('docker ps -a --filter name=6b099ed3 --format "{{.Names}} {{.Status}}"');
  console.log('project containers:\n' + r);

  // 5. Image tools
  console.log('\n=== [5/6] Image tools ===');
  r = await execCmd('docker run --rm crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/python:3.12-slim sh -c "which python3 wget curl 2>/dev/null" 2>&1', 45);
  console.log('python tools: ' + r);
  r = await execCmd('docker run --rm crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/noob_doker_base/node:20-alpine sh -c "which node wget curl 2>/dev/null" 2>&1', 45);
  console.log('node tools: ' + r);

  // 6. Disk space
  console.log('\n=== [6/6] Disk space ===');
  r = await execCmd('df -h / | tail -1');
  console.log('disk: ' + r);

  conn.end();
  console.log('\n=== ALL PRECHECKS DONE ===');
}

main().catch(e => { console.error('FATAL:', e); process.exit(1); });
