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

print('=== Current .server file ===')
print(run(f'cat /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.server'))
print()

print('=== Gateway networks ===')
print(run('docker inspect gateway-nginx --format "{{range .NetworkSettings.Networks}}{{.NetworkID}} {{.Name}}{{println}}{{end}}"'))
print()

print('=== Our project network containers ===')
print(run(f'docker network inspect {DEPLOY_ID}-network --format "{{range .Containers}}{{.Name}}{{println}}{{end}}"'))
print()

print('=== Does gateway have route to our backend? ===')
print(run(f'docker exec gateway-nginx sh -c "ping -c1 -W2 {DEPLOY_ID}-backend 2>&1 || echo NOPE"'))
print()

print('=== nginx -T grep for our server ===')
out = run(f'docker exec gateway-nginx sh -c "nginx -T 2>&1 | grep -A30 \'server_name {DEPLOY_ID}\'"')
print(out[:3000])

client.close()
