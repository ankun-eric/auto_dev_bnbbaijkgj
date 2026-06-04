"""[BUGFIX-FAMILY-STATUS-ROOT-CAUSE-V4 2026-06-03] 小程序打包"""
import os, time, secrets, zipfile, sys

ts = time.strftime('%Y%m%d_%H%M%S')
rand = secrets.token_hex(2)
name = f'miniprogram_family_status_v4_{ts}_{rand}.zip'
print('PACKING:', name)

SRC = 'miniprogram'
SKIP_DIRS = {'node_modules', '.git', 'dist', 'build', '__pycache__'}
SKIP_SUFFIX = ('.zip', '.tar.gz', '.log', '.pyc')

n = 0
with zipfile.ZipFile(name, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        for f in files:
            if f.startswith('.') or f.endswith(SKIP_SUFFIX):
                continue
            full = os.path.join(root, f)
            arc = os.path.relpath(full, SRC)
            try:
                z.write(full, arc)
                n += 1
            except OSError as e:
                print('skip', full, e, file=sys.stderr)

size = os.path.getsize(name)
print(f'DONE files={n} size={size} bytes name={name}')
with open('_mp_status_v4_zipname.txt', 'w') as f:
    f.write(name)
