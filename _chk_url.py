import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)

cmds = [
    'curl -s -o /dev/null -w "%{http_code}\\n" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/uploads/miniprogram_archive_mgr_20260529_160056_f596.zip',
    'curl -s -o /dev/null -w "%{http_code}\\n" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/uploads/miniprogram_archive_mgr_20260529_160056_f596.zip',
    'curl -s -o /dev/null -w "%{http_code}\\n" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/v1/uploads/miniprogram_archive_mgr_20260529_160056_f596.zip',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend grep -rn "uploads" /app/main.py 2>/dev/null | head -10',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend find /app -maxdepth 3 -name "main.py" -o -name "app.py" 2>/dev/null | head',
]
for c in cmds:
    print('>>>', c)
    stdin, stdout, stderr = cli.exec_command(c)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err: print('ERR:', err)
cli.close()
