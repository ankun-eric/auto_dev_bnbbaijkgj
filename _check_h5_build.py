import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

def run(cmd):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
    print('$', cmd[:160])
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err.strip():
        print('[err]', err[:500])

run('docker ps --format "{{.Names}}" | grep 6b099ed3')
run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'find /app/.next -name \"*.js\" 2>/dev/null | xargs grep -l \"mc-benefits-compare\" 2>/dev/null | head -5'")
run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'find /app/.next -name \"*.js\" 2>/dev/null | xargs grep -l \"ai-home-more-menu-item\" 2>/dev/null | head -5'")
# Also check fix: 会员中心 in MoreMenu - grep for chinese
run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'find /app/.next -name \"*.js\" 2>/dev/null | xargs grep -l \"bh-entry-member-center\" 2>/dev/null | head -5'")
c.close()
