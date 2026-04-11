import paramiko
import time

def ssh_exec(host, cmd, timeout=60):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username='ubuntu', password='Bangbang987', timeout=15)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    ssh.close()
    return out, err

def sftp_write(host, path, content):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username='ubuntu', password='Bangbang987', timeout=15)
    sftp = ssh.open_sftp()
    with sftp.file(path, 'w') as f:
        f.write(content)
    sftp.close()
    ssh.close()

FRONT_HOST = 'newbb.bangbangvip.com'

fix_script = r'''
content = open('/home/ubuntu/gateway/nginx.conf').read()

# The file is missing closing braces at the end
# The last location block for 29c7b754 catch-all is unclosed
# Then the server block and http block need closing too

# Check what the ending looks like
lines = content.rstrip().split('\n')
last_line = lines[-1].strip()
print(f"Last line: '{last_line}'")

# Count braces to figure out how many are missing
open_braces = content.count('{')
close_braces = content.count('}')
missing = open_braces - close_braces
print(f"Open braces: {open_braces}, Close braces: {close_braces}, Missing: {missing}")

if missing > 0:
    # Add the missing closing braces
    # For nginx config: location }, server }, http }
    additions = '\n'
    for i in range(missing):
        if i == 0:
            additions += '        }\n'  # location block
        elif i == 1:
            additions += '    }\n'  # server block
        elif i == 2:
            additions += '}\n'  # http block
        else:
            additions += '}\n'
    
    content = content.rstrip() + additions
    
    with open('/home/ubuntu/gateway/nginx.conf', 'r+') as f:
        f.seek(0)
        f.write(content)
        f.truncate()
    print(f'Added {missing} closing braces')
else:
    print('No missing braces')
'''

sftp_write(FRONT_HOST, '/tmp/fix_nginx.py', fix_script)
out, err = ssh_exec(FRONT_HOST, 'python3 /tmp/fix_nginx.py')
print(f"Fix: {out.strip()}")
if err:
    print(f"Err: {err.strip()}")

# Now test the config
print("\nRestarting gateway...")
out, err = ssh_exec(FRONT_HOST, "docker restart gateway-nginx 2>&1")
print(f"Restart: {out.strip()}")

time.sleep(8)

out, _ = ssh_exec(FRONT_HOST, "docker ps --filter name=gateway-nginx --format '{{.Names}}|{{.Status}}'")
print(f"Status: {out.strip()}")

if "Up" in out and "Restarting" not in out:
    print("\nVerifying access...")
    time.sleep(3)
    for path, name in [
        ("/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/", "H5"),
        ("/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/", "Admin"),
        ("/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/api/health", "API"),
    ]:
        out, _ = ssh_exec(FRONT_HOST, f"curl -sk -o /dev/null -w '%{{http_code}}' https://newbb.bangbangvip.com{path}")
        print(f"  {name}: {out.strip()}")
else:
    print("\nStill not up!")
    out, err = ssh_exec(FRONT_HOST, "docker logs gateway-nginx --tail 5 2>&1")
    print(f"Logs:\n{out}{err}")
