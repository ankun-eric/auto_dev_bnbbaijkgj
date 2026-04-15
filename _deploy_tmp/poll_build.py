import subprocess, json, time, sys, os

os.environ['GH_TOKEN'] = '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'
run_id = '24411162329'
repo = 'ankun-eric/auto_dev_bnbbaijkgj'
max_wait = 30 * 60
interval = 30
elapsed = 0

while elapsed < max_wait:
    result = subprocess.run(
        ['gh', 'run', 'view', run_id, '--repo', repo, '--json', 'status,conclusion'],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout.strip())
    status = data.get('status', '')
    conclusion = data.get('conclusion', '')
    print(f'[{elapsed}s] status={status}, conclusion={conclusion}', flush=True)
    if status == 'completed':
        print(f'BUILD_DONE|{conclusion}')
        sys.exit(0 if conclusion == 'success' else 1)
    time.sleep(interval)
    elapsed += interval

print('TIMEOUT after 30 minutes')
sys.exit(2)
