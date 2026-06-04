import paramiko, time

HOST = 'newbb.test.bangbangvip.com'
PORT = 22
USER = 'ubuntu'
PWD = 'Newbang888'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)

chan = client.get_transport().open_session()
chan.exec_command('cat /home/ubuntu/gateway/nginx.conf')
stdout = b''
while not chan.exit_status_ready():
    if chan.recv_ready():
        stdout += chan.recv(65536)
    time.sleep(0.05)
try:
    stdout += chan.recv(65536)
except:
    pass

with open('deploy/nginx_conf_remote.txt', 'w', encoding='utf-8') as f:
    f.write(stdout.decode(errors='replace'))

print('Written', len(stdout), 'bytes to deploy/nginx_conf_remote.txt')
client.close()
