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

# Upload a fix script to the server
fix_script = r'''
content = open('/home/ubuntu/gateway/nginx.conf').read()

old = '        # ===== End Project: da347c81-7ce1-4d83-bca2-aa863849b5e1 =====\n        }\n'
new = '        # ===== End Project: da347c81-7ce1-4d83-bca2-aa863849b5e1 =====\n'

if old in content:
    content = content.replace(old, new)
    with open('/home/ubuntu/gateway/nginx.conf', 'r+') as f:
        f.seek(0)
        f.write(content)
        f.truncate()
    print('Fixed extra closing brace')
else:
    print('Pattern not found - trying alternate...')
    old2 = '        # ===== End Project: da347c81-7ce1-4d83-bca2-aa863849b5e1 =====\n        }'
    new2 = '        # ===== End Project: da347c81-7ce1-4d83-bca2-aa863849b5e1 ====='
    if old2 in content:
        content = content.replace(old2, new2)
        with open('/home/ubuntu/gateway/nginx.conf', 'r+') as f:
            f.seek(0)
            f.write(content)
            f.truncate()
        print('Fixed with alternate pattern')
    else:
        print('ERROR: Could not find pattern to fix')
        # Debug: find the da347c81 end marker
        idx = content.find('End Project: da347c81')
        if idx >= 0:
            print(f'Found at index {idx}')
            print(repr(content[idx:idx+100]))
'''

sftp_write(FRONT_HOST, '/tmp/fix_brace.py', fix_script)
out, err = ssh_exec(FRONT_HOST, 'python3 /tmp/fix_brace.py')
print(f"Fix: {out.strip()}")
if err:
    print(f"Err: {err.strip()}")

print("\nTest config...")
out, err = ssh_exec(FRONT_HOST, "docker restart gateway-nginx 2>&1")
print(f"Restart: {out.strip()}")

time.sleep(8)

out, _ = ssh_exec(FRONT_HOST, "docker ps --filter name=gateway-nginx --format '{{.Names}}|{{.Status}}'")
print(f"Status: {out.strip()}")

if "Up" in out and "Restarting" not in out:
    print("\nVerifying access...")
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
