const {Client} = require('ssh2');
const conn = new Client();
function execCmd(cmd, timeout) {
  timeout = timeout || 20;
  return new Promise(function(resolve, reject) {
    conn.exec(cmd, function(err, stream) {
      if(err) { reject(err); return; }
      var out = '', errOut = '';
      stream.on('data', function(d) { out += d.toString(); });
      stream.stderr.on('data', function(d) { errOut += d.toString(); });
      stream.on('close', function() { resolve(out.trim() || errOut.trim()); });
      setTimeout(function() { reject('timeout'); }, timeout * 1000);
    });
  });
}
async function main() {
  await new Promise(function(res, rej) {
    conn.on('ready', res);
    conn.on('error', rej);
    conn.connect({
      host: 'newbb.test.bangbangvip.com',
      port: 22,
      username: 'ubuntu',
      password: 'Newbang888',
      readyTimeout: 15000
    });
  });
  console.log('CONNECTED');

  var r = await execCmd('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend printenv | grep DATABASE_URL');
  console.log('DB_URL: ' + r);

  r = await execCmd('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend cat /app/BUILD_INFO 2>/dev/null');
  console.log('Backend BUILD: ' + (r || 'NONE'));

  r = await execCmd('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-admin cat /app/BUILD_INFO 2>/dev/null');
  console.log('Admin BUILD: ' + (r || 'NONE'));

  r = await execCmd('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 cat /app/BUILD_INFO 2>/dev/null');
  console.log('H5 BUILD: ' + (r || 'NONE'));

  conn.end();
  console.log('DONE');
}
main().catch(function(e) { console.error('ERR: ' + e); process.exit(1); });
