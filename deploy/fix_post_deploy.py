import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=20)

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

cmds = [
    ('修复gateway: 删除.conf', f'rm -f /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf && echo "removed .conf"'),
    ('重载nginx', 'docker exec gateway-nginx nginx -t 2>&1 && docker exec gateway-nginx nginx -s reload 2>&1'),
    ('检查backend目录', f'docker exec {DEPLOY_ID}-backend ls /app/app/ 2>/dev/null'),
    ('检查database模块', f'docker exec {DEPLOY_ID}-backend find /app/app -name "database*" 2>/dev/null'),
    ('检查users表结构', f'docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 bini_health -e "DESCRIBE users;" 2>&1'),
    ('admin状态', f'docker inspect {DEPLOY_ID}-admin --format "{{{{.State.Health.Status}}}}" 2>/dev/null'),
    ('admin logs', f'docker logs {DEPLOY_ID}-admin --tail 15 2>&1'),
    ('h5状态', f'docker inspect {DEPLOY_ID}-h5 --format "{{{{.State.Health.Status}}}}"'),
    ('backend状态', f'docker inspect {DEPLOY_ID}-backend --format "{{{{.State.Health.Status}}}}"'),
    ('h5 logs', f'docker logs {DEPLOY_ID}-h5 --tail 10 2>&1'),
    ('backend logs', f'docker logs {DEPLOY_ID}-backend --tail 10 2>&1'),
]

for name, cmd in cmds:
    print(f'\n=== {name} ===')
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    print(out[:1200] or '(空)')
    if err:
        print(f'[stderr]: {err[:300]}')

client.close()
print('\nDone.')
