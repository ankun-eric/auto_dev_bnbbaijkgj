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
        if chan.recv_ready(): out += chan.recv(65536)
        time.sleep(0.05)
    try: out += chan.recv(65536)
    except: pass
    return out.decode(errors='replace')

print('=== Last 30 lines of nginx.conf ===')
out = run('tail -30 /home/ubuntu/gateway/nginx.conf')
print(out)

print('=== Grep for our DEPLOY_ID in nginx.conf ===')
out = run('grep -n "6b099ed3" /home/ubuntu/gateway/nginx.conf')
print(out if out.strip() else 'NOT FOUND')

print('=== Check if .server file exists ===')
out = run('ls -la /home/ubuntu/gateway/conf.d/6b099ed3*')
print(out)

print('=== nginx -T count for our domain ===')
out = run('docker exec gateway-nginx sh -c "nginx -T 2>&1 | grep -c noob-ai.test.bangbangvip.com"')
print(f'Count of noob-ai domains: {out.strip()}')

print('=== nginx -T for our specific server_name ===')
out = run('docker exec gateway-nginx sh -c "nginx -T 2>&1 | grep -A 2 server_name.*6b099ed3"')
print(out if out.strip() else 'NOT FOUND in nginx -T')

# But does it actually work?
print('=== Test access ===')
out = run('curl -sk -I https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health 2>&1 | head -15')
print(out)

client.close()
