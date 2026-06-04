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

# Check containers
print("=== Containers ===")
print(run(f"docker ps -a --filter name={DEPLOY_ID} --format '{{{{.Names}}}} {{{{.Status}}}}'"))
print()

# Check project directory
print("=== Project Directory ===")
print(run(f"ls -la /home/ubuntu/{DEPLOY_ID}/ 2>&1 | head -20"))
print()

# Check gateway config for this project
print("=== Gateway Config ===")
print(run(f"ls -la /home/ubuntu/gateway/conf.d/*{DEPLOY_ID}* 2>&1"))
print()

# Check if nginx.conf already has server block for this project
print("=== Nginx conf check ===")
print(run(f"grep -n '{DEPLOY_ID}' /home/ubuntu/gateway/nginx.conf 2>&1"))

client.close()
