import paramiko, time
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
time.sleep(20)
BASE = 'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'

tests = [
    ('GET', '/api/admin/home_safety/callback_log', '401', None),
    ('POST', '/api/admin/home_safety/callback_config/precheck', '401', '{}'),
    ('POST', '/api/home_safety/callback/alarm', '200',
     '{"dataType":"__precheck__","msgId":"smoke-001","param":{}}'),
    ('GET', '/admin/home-safety', '200/302', None),
]
for method, path, expected, body in tests:
    if method == 'GET':
        cmd = f"curl -s -o /dev/null -w '%{{http_code}}' '{BASE}{path}'"
    else:
        cmd = f"curl -s -o /dev/null -w '%{{http_code}}' -X POST '{BASE}{path}' -H 'Content-Type: application/json' -d '{body}'"
    _, o, _ = c.exec_command(cmd, timeout=20)
    code = o.read().decode().strip()
    print(f"{method} {path} => {code} (want {expected})")

# 详细看一次 callback alarm precheck
cmd = (f"curl -s -X POST '{BASE}/api/home_safety/callback/alarm' "
       "-H 'Content-Type: application/json' "
       """-d '{"dataType":"__precheck__","msgId":"smoke-002","param":{}}'""")
_, o, _ = c.exec_command(cmd, timeout=30)
print("callback precheck body:", o.read().decode("utf-8","replace"))

c.close()
