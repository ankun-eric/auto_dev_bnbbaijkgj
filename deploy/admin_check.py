"""Check and create admin account."""
import paramiko, json, base64

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def run(cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    return out, err

# Write a Python script to the backend container and execute it
script = '''
import urllib.request, json

def try_login(data, label):
    d = json.dumps(data).encode()
    req = urllib.request.Request('http://localhost:8000/api/auth/login', data=d,
        headers={'Content-Type':'application/json'})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"Login({label}): OK status={resp.status} body={resp.read().decode()[:200]}")
    except urllib.error.HTTPError as e:
        print(f"Login({label}): HTTP {e.code} body={e.read().decode()[:200]}")
    except Exception as e:
        print(f"Login({label}): Error {e}")

try_login({"phone":"13800000000","password":"admin123"}, "phone")
try_login({"username":"admin","password":"admin123"}, "username")
try_login({"phone":"13800000000","code":"123456"}, "sms_code")

# Try register
data = json.dumps({"phone":"13800000000","password":"admin123","nickname":"Admin","sms_code":"123456"}).encode()
req = urllib.request.Request('http://localhost:8000/api/auth/register', data=data,
    headers={'Content-Type':'application/json'})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    print(f"Register: OK status={resp.status} body={resp.read().decode()[:200]}")
except urllib.error.HTTPError as e:
    print(f"Register: HTTP {e.code} body={e.read().decode()[:200]}")
except Exception as e:
    print(f"Register: Error {e}")
'''

# Encode and send via SFTP
sftp = ssh.open_sftp()
sftp.putfo(__import__('io').BytesIO(script.encode()), '/tmp/admin_check.py')
sftp.close()
run(f"docker cp /tmp/admin_check.py {DEPLOY_ID}-backend:/tmp/admin_check.py")
out, err = run(f"docker exec {DEPLOY_ID}-backend python3 /tmp/admin_check.py")
print(f"OUT: {out}")
print(f"ERR: {err}")

ssh.close()
