const { spawn } = require('child_process');
const fs = require('fs');

const HOST = '134.175.97.26';
const USER = 'ubuntu';
const PASS = 'Newbang888';
const PORT = '22';

const log = (msg) => {
    console.log(msg);
    fs.appendFileSync('C:/auto_output/bnbbaijkgj/deploy/ssh_node.log', msg + '\n');
};

fs.writeFileSync('C:/auto_output/bnbbaijkgj/deploy/ssh_node.log', '');

log('Starting SSH connection...');

const ssh = spawn('ssh', [
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'UserKnownHostsFile=/dev/null',
    '-o', 'ConnectTimeout=10',
    '-o', 'PasswordAuthentication=yes',
    '-o', 'PubkeyAuthentication=no',
    '-o', 'PreferredAuthentications=password',
    '-p', PORT,
    USER + '@' + HOST,
    'echo OK'
]);

let allOutput = '';
let resolved = false;

ssh.stdout.on('data', (data) => {
    const s = data.toString();
    log('STDOUT: ' + s.trim());
    allOutput += s;
});

ssh.stderr.on('data', (data) => {
    const s = data.toString();
    log('STDERR: ' + s.trim());
    allOutput += s;
});

ssh.on('close', (code) => {
    if (!resolved) {
        resolved = true;
        log('CLOSE: exit code=' + code);
        log('FULL_OUTPUT: ' + allOutput);
        process.exit(code || 0);
    }
});

ssh.on('error', (err) => {
    if (!resolved) {
        resolved = true;
        log('ERROR: ' + err.message);
        process.exit(1);
    }
});

// Write password after a short delay to ensure SSH is ready
setTimeout(() => {
    log('Sending password...');
    ssh.stdin.write(PASS + '\n');
    ssh.stdin.end();
}, 2000);

setTimeout(() => {
    if (!resolved) {
        resolved = true;
        log('TIMEOUT: 20 seconds exceeded');
        ssh.kill();
        process.exit(1);
    }
}, 20000);
