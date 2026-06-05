import paramiko, sys
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=15)
print('connected', flush=True)

def run(cmd):
    print(f'\n>>> {cmd[:100]}', flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print(f'EXIT={ec}', flush=True)
    if out.strip(): print(out[:800], flush=True)
    if err.strip() and ec != 0: print('ERR:', err[:400], flush=True)
    return ec, out, err

run('docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-admin --tail 20')
run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-admin ls -la /app/')
run('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-admin cat /app/package.json 2>/dev/null | head -5')
run('docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-admin --format "{{json .State.Health}}" | python3 -m json.tool')

ssh.close()
print('\ndone', flush=True)
