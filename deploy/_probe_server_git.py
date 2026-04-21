import sys
sys.path.insert(0, '.')
from ssh_helper import create_client, run_cmd

ssh = create_client()
for cmd in [
    'curl -s -o /dev/null -w "%{http_code}\\n" --max-time 10 https://github.com',
    'git --version',
    'env | grep -i proxy || true',
    'cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && git remote -v',
]:
    print(f'$ {cmd}')
    out, err, code = run_cmd(ssh, cmd, timeout=30)
    print(out)
    if err.strip(): print('STDERR:', err)
    print('---')
ssh.close()
