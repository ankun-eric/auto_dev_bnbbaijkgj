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

# Check if nginx.conf includes our .server file
print('=== grep for includes in nginx.conf ===')
print(run('grep -n "include.*conf.d\|include.*server" /home/ubuntu/gateway/nginx.conf'))
print()

# Check what nginx actually has loaded for our domain
print('=== nginx -T full output (looking for our server_name) ===')
out = run('docker exec gateway-nginx sh -c "nginx -T 2>&1"')
# Search for our domain in output
lines = out.split('\n')
for i, line in enumerate(lines):
    if DEPLOY_ID in line:
        # Print context
        start = max(0, i-2)
        end = min(len(lines), i+5)
        for j in range(start, end):
            print(f'  {j}: {lines[j]}')
        print('---')
print()

# Check if we can curl the domain through gateway
print('=== Test local access via gateway ===')
print(run(f'docker exec gateway-nginx sh -c "curl -s -o /dev/null -w \'%{{http_code}}\' http://{DEPLOY_ID}-backend:8000/api/health 2>&1"'))
print()

# Check if the service is accessible from within the server but through the domain
print('=== Test domain access ===')
print(run('curl -s -o /dev/null -w "%{http_code}" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health -k 2>&1'))
print()

client.close()
