import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=15)

urls = [
    ('Backend /api/docs', 'curl -s -o /dev/null -w "%{http_code}" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/docs'),
    ('H5 /family-invite', 'curl -s -o /dev/null -w "%{http_code}" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/family-invite'),
    ('H5 /family-auth', 'curl -s -o /dev/null -w "%{http_code}" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/family-auth'),
    ('Admin /settings', 'curl -s -o /dev/null -w "%{http_code}" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/settings'),
    ('Protocol API', 'curl -s -o /dev/null -w "%{http_code}" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/public/protocol/healthDataAuthorization'),
    ('Invitation API', 'curl -s -o /dev/null -w "%{http_code}" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/invitation/test123'),
]

for name, cmd in urls:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    code = stdout.read().decode().strip()
    print(f'{name}: {code}')

ssh.close()
print('\nDeploy verification complete.')
