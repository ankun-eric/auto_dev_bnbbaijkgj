import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
cmds = [
    # h5 container details
    f'sudo -n docker inspect {PROJECT_ID}-h5 --format "{{{{json .Mounts}}}}"',
    f'sudo -n docker inspect {PROJECT_ID}-h5 --format "{{{{.Config.Image}}}} CMD={{{{.Config.Cmd}}}} ENTRY={{{{.Config.Entrypoint}}}} WORKDIR={{{{.Config.WorkingDir}}}}"',
    f'sudo -n docker exec {PROJECT_ID}-h5 ls -la /app/public/ | head -20',
    f'sudo -n docker exec {PROJECT_ID}-h5 sh -c "ls -la /app/public/miniprogram_20260517_123547_1156.zip 2>&1 || true"',
    # gateway nginx config probe
    'sudo -n docker exec gateway sh -c "ls /etc/nginx/conf.d/ 2>&1 | head -10"',
    f'sudo -n docker exec gateway sh -c "grep -rn \\"{PROJECT_ID}\\" /etc/nginx/ 2>/dev/null | head -30"',
]
for cmd in cmds:
    print('==>', cmd)
    i, o, e = c.exec_command(cmd, timeout=30)
    print('OUT:', o.read().decode(errors='replace')[:2500])
    err = e.read().decode(errors='replace')
    if err:
        print('ERR:', err[:500])
    print()
c.close()
