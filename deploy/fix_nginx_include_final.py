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
    return out.decode(errors='replace'), chan.exit_status

# Check current state
out, ec = run(f'grep -n "{DEPLOY_ID}" /home/ubuntu/gateway/nginx.conf')
print(f'Current include: {out.strip() if out.strip() else "NOT FOUND"}')

if DEPLOY_ID not in out:
    print('Adding include line...')
    # Write a simpler fix script to server
    script = """import sys
with open("/home/ubuntu/gateway/nginx.conf", "r") as f:
    content = f.read()
include_line = "    include /etc/nginx/conf.d/""" + DEPLOY_ID + """.server;\\n"
if include_line.strip() not in content:
    last_brace = content.rfind(chr(125))
    if last_brace > 0:
        content = content[:last_brace] + include_line + content[last_brace:]
        with open("/home/ubuntu/gateway/nginx.conf", "w") as f:
            f.write(content)
        print("Added include line")
    else:
        print("ERROR: closing brace not found")
        sys.exit(1)
else:
    print("Include already present")
"""
    # Write script to server
    cmd = "cat > /tmp/add_include.py << 'PYEOF'\n" + script + "\nPYEOF"
    out, ec = run(cmd)
    print(f'Write: {out.strip()}')
    
    # Run script
    out, ec = run('python3 /tmp/add_include.py')
    print(f'Result: {out.strip()}')
    
    # Test nginx config
    out, ec = run('docker exec gateway-nginx nginx -t 2>&1')
    print(f'Nginx -t: {out.strip()[:300]}')
    
    if ec == 0:
        out, ec = run('docker exec gateway-nginx nginx -s reload 2>&1')
        print(f'Reload: {out.strip()[:200]}')
        
        # Verify
        time.sleep(2)
        out, ec = run(f'curl -sk -o /dev/null -w "%{{http_code}}" https://{DEPLOY_ID}.noob-ai.test.bangbangvip.com/api/health')
        print(f'HTTPS test: HTTP {out.strip()}')
    else:
        print('Nginx config test failed!')

client.close()
