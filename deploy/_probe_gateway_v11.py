"""通过 gateway 容器看 nginx 配置"""
import paramiko

HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=22, username=USER, password=PWD, timeout=30, allow_agent=False, look_for_keys=False)

# locate gateway container
_, o, _ = c.exec_command('docker ps --format "{{.Names}}" | grep -iE "gateway|nginx|traefik"')
print('---gateway containers---')
print(o.read().decode('utf-8', errors='replace'))

# look at host gateway dir
_, o, _ = c.exec_command('ls -la /home/ubuntu/gateway/ 2>/dev/null; ls -la /home/ubuntu/gateway/conf.d/ 2>/dev/null | head -40')
print('---gateway host dir---')
print(o.read().decode('utf-8', errors='replace'))

# find proj-specific conf
_, o, _ = c.exec_command(f'grep -lr "{DEPLOY_ID}" /home/ubuntu/gateway/ 2>/dev/null | head -5')
print('---grep DEPLOY_ID in gateway---')
print(o.read().decode('utf-8', errors='replace'))

c.close()
