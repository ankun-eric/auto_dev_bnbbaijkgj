import paramiko, time, sys

host = 'newbb.test.bangbangvip.com'
user = 'ubuntu'
pwd = 'Newbang888'
dep_id = '6b099ed3-7175-4a78-91f4-44570c84ed27'
proj = f'/home/ubuntu/{dep_id}'

def run(cmd, timeout=120):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, 22, user, pwd, timeout=15)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    client.close()
    return out, err

print('=== Step 1: docker compose down ===', flush=True)
out, err = run(f'cd {proj} && docker compose -f docker-compose.prod.yml down 2>&1', timeout=30)
print(out[:500] if out else '(no output)')
if err: print('err:', err[:300])

print('=== Step 2: build backend ===', flush=True)
out, err = run(f'cd {proj} && docker compose -f docker-compose.prod.yml build --no-cache backend 2>&1 | tail -30', timeout=600)
print(out[-1000:] if len(out) > 1000 else out)
if err: print('err:', err[-500:])

print('=== Step 3: build h5 ===', flush=True)
out, err = run(f'cd {proj} && docker compose -f docker-compose.prod.yml build --no-cache h5 2>&1 | tail -30', timeout=600)
print(out[-1000:] if len(out) > 1000 else out)
if err: print('err:', err[-500:])

print('=== Step 4: build admin ===', flush=True)
out, err = run(f'cd {proj} && docker compose -f docker-compose.prod.yml build --no-cache admin 2>&1 | tail -30', timeout=600)
print(out[-1000:] if len(out) > 1000 else out)
if err: print('err:', err[-500:])

print('=== Step 5: up -d ===', flush=True)
out, err = run(f'cd {proj} && docker compose -f docker-compose.prod.yml up -d 2>&1', timeout=60)
print(out[:500] if out else '(no output)')
if err: print('err:', err[:300])

print('=== Step 6: wait healthcheck ===', flush=True)
for i in range(30):
    time.sleep(5)
    out, err = run(f'cd {proj} && docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null', timeout=15)
    count = out.count('"Health":"healthy"')
    total = out.count('"Name"')
    print(f'  [{i+1}/30] {count}/{total} healthy', flush=True)
    if count >= total and total > 0:
        print('ALL HEALTHY!', flush=True)
        break

print('=== Step 7: connect gateway network ===', flush=True)
out, err = run(f'docker network connect {dep_id}-network gateway-nginx 2>&1 || echo already_connected', timeout=15)
print(out[:200])

print('=== Step 8: verify ===', flush=True)
out, err = run(f'docker exec {dep_id}-backend python3 -c "import urllib.request; r=urllib.request.urlopen(\"http://localhost:8000/api/health\"); print(r.read().decode())"', timeout=15)
print('Backend health:', out.strip())

print('DONE', flush=True)
