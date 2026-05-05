import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=20)

cmds = [
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'ls /app/.next/server/app/login.html 2>/dev/null; ls /app/.next/server/app/login/ 2>/dev/null; ls /app/.next/server/app/ 2>/dev/null | head -30'",
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'find /app/.next -path \"*login*\" -name \"*.js\" 2>/dev/null | head -5'",
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'grep -rl top-brand /app/.next/static/chunks/ 2>/dev/null | head -3; echo ---; grep -rl 2fb56a /app/.next/static/chunks/ 2>/dev/null | head -3'",
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'grep -l 同意并登录 /app/.next/static/chunks/app/login/*.js 2>/dev/null; grep -rl 同意并登录 /app/.next/static/chunks/ 2>/dev/null | head -3'",
]
for cmd in cmds:
    print('===', cmd[:120])
    _, o, e = ssh.exec_command(cmd, timeout=60)
    print(o.read().decode('utf-8', 'replace'))
    err = e.read().decode('utf-8', 'replace')
    if err.strip():
        print('[STDERR]', err)
ssh.close()
