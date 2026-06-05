const {Client} = require('ssh2');
const c = new Client();
c.on('ready', function() {
  const cmd = 'curl -s -X POST https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/auth/login -H "Content-Type: application/json" -d \'{"username":"admin","password":"admin123"}\' 2>&1';
  c.exec(cmd, function(err, stream) {
    let out = '';
    stream.on('data', function(d) { out += d.toString(); });
    stream.on('close', function() {
      console.log('Login response:', out.substring(0, 500));
      c.end();
    });
  });
});
c.connect({host:'newbb.test.bangbangvip.com', port:22, username:'ubuntu', password:'Newbang888', readyTimeout:10000});
