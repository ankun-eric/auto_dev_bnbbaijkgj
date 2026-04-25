"""Fix stale bind mount: gateway container's /data/static lost view of host's
static dir because the host directory inode changed after container start.

We restart the gateway container to refresh the mount.
"""
import paramiko
import time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=60)


def run(cmd, timeout=120):
    print('### ' + cmd)
    i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode('utf-8', 'replace')
    err = e.read().decode('utf-8', 'replace')
    code = o.channel.recv_exit_status()
    if out:
        print(out[-1500:])
    if err:
        print('[err]', err[-400:])
    print('[exit', code, ']')
    return code, out, err


run('docker exec gateway ls -la /data/static/ 2>&1')
run('docker restart gateway')
print('Waiting 5s for gateway to come up...')
time.sleep(5)
run('docker exec gateway ls -la /data/static/downloads/ 2>&1 | head -10')
run('curl -sI -k https://localhost/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_latest.zip -H "Host: newbb.test.bangbangvip.com" 2>&1 | head -10')

c.close()
