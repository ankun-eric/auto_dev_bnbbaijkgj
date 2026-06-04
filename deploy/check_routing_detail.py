import paramiko, time

HOST = 'newbb.test.bangbangvip.com'
PORT = 22
USER = 'ubuntu'
PWD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)

def run(cmd):
    chan = client.get_transport().open_session()
    chan.exec_command(cmd)
    out = b''
    while not chan.exit_status_ready():
        if chan.recv_ready():
            out += chan.recv(65536)
        time.sleep(0.05)
    try:
        out += chan.recv(65536)
    except:
        pass
    return out.decode(errors='replace')

# Check active .conf files
print('=== Active .conf files ===')
print(run('ls -la /home/ubuntu/gateway/conf.d/*.conf 2>&1'))
print()

# Check .server files
print('=== .server files ===')
print(run('ls -la /home/ubuntu/gateway/conf.d/*.server 2>&1'))
print()

# Check if nginx has our server loaded via conf.d include
print('=== Check nginx loaded config for our domain ===')
out = run('docker exec gateway-nginx sh -c "nginx -T 2>&1"')
if DEPLOY_ID in out:
    idx = out.find(DEPLOY_ID)
    print(out[max(0,idx-200):idx+500])
else:
    print('NOT FOUND in nginx -T')
print()

# Check hostname resolution
print('=== DNS check ===')
print(run(f'curl -vIk https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com/api/health 2>&1 | head -30'))
print()

# Check if there is something proxying
print('=== Direct backend health check ===')
print(run(f'docker exec {DEPLOY_ID}-backend python -c "import urllib.request; print(urllib.request.urlopen(\\"http://localhost:8000/api/health\\").read())" 2>&1'))

client.close()
