import subprocess, sys, json
from datetime import datetime

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
backup_tag = f"backup-{datetime.now().strftime('%Y%m%d%H%M%S')}"
print(f"BACKUP_TAG={backup_tag}")

containers = ['backend', 'h5', 'admin']
for name in containers:
    cname = f'{DEPLOY_ID}-{name}'
    try:
        r = subprocess.run(
            ['docker', 'inspect', '--format={{.Image}}', cname],
            capture_output=True, text=True, timeout=15
        )
        img_id = r.stdout.strip()
        if img_id:
            subprocess.run(
                ['docker', 'tag', img_id, f'{cname}:{backup_tag}'],
                check=True, timeout=15
            )
            print(f"backup: {cname} -> {backup_tag}")
    except Exception as e:
        print(f"skip {cname}: {e}")

print("backup_done")
