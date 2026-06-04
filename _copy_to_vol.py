import paramiko, time, urllib.request, ssl, sys
ZIP_NAME = open('_zip_name.txt').read().strip()
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
URL = f'https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/uploads/{ZIP_NAME}'

REMOTE_TMP = f'/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/uploads/{ZIP_NAME}'

last_err = None
for attempt in range(3):
    try:
        cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cli.connect(HOST, username=USER, password=PWD, timeout=30)
        cmd = f'docker cp {REMOTE_TMP} 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/uploads/{ZIP_NAME} && docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend ls -la /app/uploads/{ZIP_NAME}'
        stdin, stdout, stderr = cli.exec_command(cmd)
        print(stdout.read().decode())
        err = stderr.read().decode()
        if err: print('ERR:', err)
        cli.close()
        break
    except Exception as e:
        last_err = e
        print('attempt', attempt+1, 'failed:', e)
        time.sleep(3)
else:
    raise last_err

ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
req = urllib.request.Request(URL, method='HEAD')
for attempt in range(3):
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            print('HTTP', r.status, 'len=', r.headers.get('Content-Length'))
            if r.status == 200:
                print('OK_URL=' + URL)
                sys.exit(0)
    except Exception as e:
        print('verify', attempt+1, 'failed:', e); time.sleep(3)
sys.exit(2)
