import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com',username='ubuntu',password='Newbang888',timeout=20)
def r(cmd, t=20):
    _,o,e=c.exec_command(cmd,timeout=t)
    print('$',cmd)
    print(o.read().decode('utf-8','replace'))
    err=e.read().decode('utf-8','replace')
    if err.strip(): print('stderr:',err[-1500:])

r('ls -lh /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/ 2>&1 | head -20')
r('docker ps --filter ancestor=flutter-builder:latest --format "{{.ID}}|{{.Status}}|{{.Names}}"')
r('tail -10 /tmp/flutter_build_h5co.log 2>&1 || echo NO_LOG')
r('ls -lh /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/flutter_app/build/app/outputs/flutter-apk/ 2>&1 || echo NO_BUILD')
c.close()
