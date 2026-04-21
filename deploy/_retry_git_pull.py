import sys, time
sys.path.insert(0, '.')
from ssh_helper import create_client, run_cmd

PROJ_DIR = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'

ssh = create_client()
for attempt in range(1, 10):
    print(f'\n=== Attempt {attempt} ===')
    out, err, code = run_cmd(
        ssh,
        f'cd {PROJ_DIR} && timeout 90 git fetch origin master && git reset --hard origin/master && git log -1 --oneline',
        timeout=120,
    )
    print(out)
    if err.strip(): print('STDERR:', err)
    if code == 0:
        print('SUCCESS')
        break
    print(f'exit={code}, retrying in 15s...')
    time.sleep(15)
else:
    print('All attempts failed')
    sys.exit(1)
ssh.close()
