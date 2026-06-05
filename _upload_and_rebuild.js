const fs = require('fs');
const path = require('path');
const { Client } = require('ssh2');

const SERVER = {
  host: 'newbb.test.bangbangvip.com',
  port: 22,
  username: 'ubuntu',
  password: 'Newbang888'
};

const DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27';
const SERVER_PROJECT_DIR = `/home/ubuntu/${DEPLOY_ID}`;

const FILES_TO_UPLOAD = [
  'backend/app/services/family_status_constants.py',
  'backend/app/services/family_member_status.py',
  'backend/app/api/family.py',
  'backend/app/api/family_management.py',
  'backend/app/api/family_member_v2.py',
  'backend/app/api/admin.py',
  'backend/app/api/health_profile.py',
  'backend/app/api/guardian_system_v13.py',
  'backend/app/api/guardian_bugfix_v1.py',
  'backend/app/api/reverse_guardian.py',
  'backend/app/api/users.py',
  'backend/app/models/models.py',
  'backend/app/core/security.py',
  'backend/app/main.py',
];

const conn = new Client();
conn.on('ready', () => {
  console.log('SSH 连接成功');
  
  // Use SFTP to upload files
  conn.sftp((err, sftp) => {
    if (err) {
      console.error('SFTP 错误:', err);
      conn.end();
      return;
    }
    
    let uploaded = 0;
    let total = FILES_TO_UPLOAD.length;
    
    FILES_TO_UPLOAD.forEach((file) => {
      const localPath = path.join(__dirname, file);
      const remotePath = `${SERVER_PROJECT_DIR}/${file}`;
      
      const content = fs.readFileSync(localPath, 'utf8');
      
      sftp.writeFile(remotePath, content, { encoding: 'utf8' }, (err) => {
        if (err) {
          console.error(`上传失败 ${file}:`, err.message);
        } else {
          console.log(`上传成功: ${file}`);
        }
        uploaded++;
        if (uploaded >= total) {
          console.log('所有文件上传完成');
          sftp.end();
          rebuildContainer(conn);
        }
      });
    });
  });
});

function rebuildContainer(conn) {
  console.log('开始重建后端容器...');
  const commands = [
    `cd ${SERVER_PROJECT_DIR}`,
    `BUILD_COMMIT=$(git log -1 --format="%H" 2>/dev/null || echo "rebuild-$(date +%Y%m%d%H%M%S)")`,
    `export BUILD_COMMIT`,
    `docker compose -f docker-compose.prod.yml up -d --no-deps --build backend`,
  ];
  
  const cmd = commands.join(' && ');
  conn.exec(cmd, { pty: true }, (err, stream) => {
    if (err) {
      console.error('执行命令错误:', err);
      conn.end();
      return;
    }
    stream.on('data', (data) => { process.stdout.write('' + data); });
    stream.stderr.on('data', (data) => { process.stderr.write('' + data); });
    stream.on('close', (code) => {
      console.log('重建完成，exit code:', code);
      // Wait for health check
      setTimeout(() => {
        conn.exec('docker ps --format "{{.Names}} {{.Status}}"', (err, stream) => {
          if (err) { conn.end(); return; }
          stream.on('data', (data) => { console.log('' + data); });
          stream.on('close', () => conn.end());
        });
      }, 5000);
    });
  });
}

conn.on('error', (err) => {
  console.error('SSH 连接错误:', err.message);
  if (err.message.includes('Timed out') || err.message.includes('ETIMEDOUT')) {
    console.log('连接超时，请稍后重试');
  }
});

console.log('正在连接到服务器...');
conn.connect(SERVER);
