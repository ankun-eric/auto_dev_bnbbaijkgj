
const { Client } = require('ssh2');
const c = new Client();

c.on('ready', function() {
  c.exec('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 ls -la /app/.next/server/app/family/ 2>&1', function(err, stream) {
    let o = '';
    stream.on('data', function(d) { o += d.toString(); });
    stream.on('close', function() {
      console.log('H5 /family build output:', o);
      
      c.exec('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 wget -qO- http://localhost:3001/family 2>&1 | head -5', function(err2, stream2) {
        let o2 = '';
        stream2.on('data', function(d) { o2 += d.toString(); });
        stream2.on('close', function() {
          console.log('Internal /family response:', o2.slice(0, 300));
          
          // Check if family page exists in source
          c.exec('ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/h5-web/src/app/family/ 2>&1', function(err3, stream3) {
            let o3 = '';
            stream3.on('data', function(d) { o3 += d.toString(); });
            stream3.on('close', function() {
              console.log('Server source /family:', o3);
              c.end();
            });
          });
        });
      });
    });
  });
});

c.connect({
  host: 'newbb.test.bangbangvip.com',
  port: 22,
  username: 'ubuntu',
  password: 'Newbang888',
  readyTimeout: 10000
});
