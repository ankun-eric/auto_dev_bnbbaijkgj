import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)

cmds = [
    'docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --format "{{json .Mounts}}" | python3 -m json.tool',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend ls /app/uploads/ 2>&1 | head -20',
    'curl -s -o /dev/null -w "%{http_code}\\n" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/uploads/miniprogram_20260525_011224_e0b8.zip',
]
for c in cmds:
    print('>>>', c)
    stdin, stdout, stderr = cli.exec_command(c)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err: print('ERR:', err)
cli.close()
