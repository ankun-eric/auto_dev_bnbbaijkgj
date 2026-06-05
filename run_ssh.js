const { execSync } = require('child_process');
const fs = require('fs');

const cmd = process.argv[2];
const timeout = parseInt(process.argv[3]) || 120000;

if (!cmd) {
    console.error('Usage: node run_ssh.js "command" [timeout_ms]');
    process.exit(1);
}

const sshCmd = `ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o PasswordAuthentication=no -o PubkeyAuthentication=yes -o IdentitiesOnly=yes -i C:\\Users\\Administrator\\.ssh\\id_rsa -o ServerAliveInterval=2 -o ServerAliveCountMax=2 -p 22 ubuntu@134.175.97.26 "${cmd.replace(/"/g, '\\"')}"`;

const tmpFile = 'C:/auto_output/bnbbaijkgj/.ssh_tmp_output.txt';

try {
    const result = execSync(`${sshCmd} > "${tmpFile}" 2>&1`, { timeout, shell: 'cmd.exe' });
    console.log(result.toString());
} catch (e) {
    // SSH returns non-zero for many reasons, but we still want the output
}

try {
    const output = fs.readFileSync(tmpFile, 'utf8');
    console.log(output);
    fs.unlinkSync(tmpFile);
} catch (e) {
    // ignore
}
