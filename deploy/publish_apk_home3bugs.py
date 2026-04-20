"""Publish the already-built home3bugs APK to static/downloads/.

The v3 build actually succeeded (79.2MB APK built in 469s at commit e556fed).
Just need to copy it to static/downloads/ and verify URL.
"""
import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DOMAIN = "newbb.test.bangbangvip.com"
PROJECT = f"/home/ubuntu/{DEPLOY_ID}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=60)

def run(cmd, timeout=300):
    print(f"\n>>> {cmd[:260]}")
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode(errors='ignore')
    err = e.read().decode(errors='ignore')
    if out.strip():
        print(out[-4000:])
    if err.strip():
        print('STDERR:', err[-1500:])
    return out

# Check built apk
built = run(f'ls -la {PROJECT}/flutter_app/build/app/outputs/flutter-apk/app-release.apk 2>&1')
if 'app-release.apk' not in built or 'No such file' in built:
    print("!!! No built APK present on server, must rebuild !!!")
    c.close()
    raise SystemExit(2)

# Verify the build source is at commit e556fed (home3bugs)
run(f'cd {PROJECT} && git log -1 --format="%H %s" 2>&1')

# Copy to downloads
ts = time.strftime('%Y%m%d-%H%M%S')
apk_name = f"bini_health_android-home3bugs-{ts}.apk"
run(
    f'cp {PROJECT}/flutter_app/build/app/outputs/flutter-apk/app-release.apk '
    f'{PROJECT}/static/downloads/{apk_name} && '
    f'cp {PROJECT}/flutter_app/build/app/outputs/flutter-apk/app-release.apk '
    f'{PROJECT}/static/downloads/bini_health_android_latest.apk && '
    f'chmod 644 {PROJECT}/static/downloads/*.apk && '
    f'ls -lh {PROJECT}/static/downloads/*.apk'
)

# also sync to static/apk
run(
    f'cp {PROJECT}/flutter_app/build/app/outputs/flutter-apk/app-release.apk '
    f'{PROJECT}/static/apk/{apk_name} && '
    f'cp {PROJECT}/flutter_app/build/app/outputs/flutter-apk/app-release.apk '
    f'{PROJECT}/static/apk/bini_health.apk && '
    f'chmod 644 {PROJECT}/static/apk/*.apk && '
    f'ls -lh {PROJECT}/static/apk/*.apk | tail -5'
)

# Get exact size
size_out = run(f'stat -c "%s" {PROJECT}/static/downloads/{apk_name}')
try:
    size_bytes = int(size_out.strip().splitlines()[-1])
    size_mb = size_bytes / 1024 / 1024
except Exception:
    size_mb = -1

# Verify URL via curl (from server - bypasses any DNS nuances but tests nginx)
url = f"https://{DOMAIN}/autodev/{DEPLOY_ID}/static/downloads/{apk_name}"
url_latest = f"https://{DOMAIN}/autodev/{DEPLOY_ID}/static/downloads/bini_health_android_latest.apk"
run(f'curl -sS -o /dev/null -w "HTTP %{{http_code}} size=%{{size_download}} time=%{{time_total}}s\\n" -I "{url}"')
run(f'curl -sS -o /dev/null -w "HTTP %{{http_code}} size=%{{size_download}} time=%{{time_total}}s\\n" -I "{url_latest}"')

print("\n==================== PUBLISHED ====================")
print(f"APK: {apk_name}")
print(f"Size: {size_mb:.2f} MB")
print(f"URL (unique):  {url}")
print(f"URL (latest):  {url_latest}")

c.close()
