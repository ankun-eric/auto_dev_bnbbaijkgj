const { Client } = require('ssh2');

const HOST = process.argv[2] || 'newbb.test.bangbangvip.com';
const PORT = parseInt(process.argv[3]) || 22;
const USER = process.argv[4] || 'ubuntu';
const PASS = process.argv[5] || 'Newbang888';
const CMD = process.argv[6];
const TIMEOUT = parseInt(process.argv[7]) || 30000;

if (!CMD) {
    process.stderr.write('Usage: node ssh_exec.js [host] [port] [user] [pass] "command" [timeout_ms]\n');
    process.exit(1);
}

const conn = new Client();
let output = '';
let errorOutput = '';
let done = false;
let connected = false;

process.stdout.write('CONNECTING to ' + HOST + ':' + PORT + '\n');

conn.on('ready', () => {
    connected = true;
    process.stdout.write('SSH_READY\n');
    conn.exec(CMD, (err, stream) => {
        if (err) {
            process.stderr.write('EXEC_ERROR: ' + err.message + '\n');
            conn.end();
            process.exit(1);
        }
        stream.on('close', (code, signal) => {
            process.stdout.write('STREAM_CLOSE code=' + code + ' signal=' + signal + '\n');
            conn.end();
            if (!done) {
                done = true;
                process.stdout.write('OUTPUT_START\n' + output + errorOutput + 'OUTPUT_END\n');
                process.exit(code || 0);
            }
        }).on('data', (data) => {
            output += data.toString();
        }).stderr.on('data', (data) => {
            errorOutput += data.toString();
        });
    });
});

conn.on('error', (err) => {
    if (!done) {
        done = true;
        process.stderr.write('SSH_CONN_ERROR: ' + err.message + '\n');
        process.exit(1);
    }
});

conn.on('keyboard-interactive', (name, instructions, instructionsLang, prompts, finish) => {
    finish([PASS]);
});

conn.on('banner', (msg) => {
    process.stdout.write('BANNER: ' + msg.trim() + '\n');
});

conn.connect({
    host: HOST,
    port: PORT,
    username: USER,
    password: PASS,
    readyTimeout: 30000,
    tryKeyboard: true,
    keepaliveInterval: 5000,
});

setTimeout(() => {
    if (!done) {
        done = true;
        process.stdout.write('TIMEOUT_FIRED connected=' + connected + '\n');
        process.stdout.write('PARTIAL_OUTPUT:\n' + output + errorOutput + '\n');
        conn.end();
        process.exit(0);
    }
}, TIMEOUT);
