"""Verify APK actually downloads (full content fetch) via working URL path."""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=60)

def run(cmd, timeout=180):
    print(f"\n>>> {cmd[:240]}")
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode(errors='ignore')
    err = e.read().decode(errors='ignore')
    if out.strip(): print(out[-3000:])
    if err.strip(): print('STDERR:', err[-1000:])
    return out

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DOMAIN = "newbb.test.bangbangvip.com"
APK = "bini_health_android-home3bugs-20260421-034208.apk"

# Server-side: verify via GET -I produces size-less HEAD, do real GET and drop body
# URL under /apk/
u1 = f"https://{DOMAIN}/autodev/{DEPLOY_ID}/apk/{APK}"
u2 = f"https://{DOMAIN}/autodev/{DEPLOY_ID}/apk/bini_health.apk"

# Also copy to static/downloads (served at /downloads/) for Leader's requested pattern
run(
    f'cp /home/ubuntu/{DEPLOY_ID}/static/apk/{APK} /home/ubuntu/{DEPLOY_ID}/static/downloads/{APK} 2>&1 && '
    f'cp /home/ubuntu/{DEPLOY_ID}/static/apk/bini_health.apk /home/ubuntu/{DEPLOY_ID}/static/downloads/bini_health_android_latest.apk 2>&1 && '
    f'chmod 644 /home/ubuntu/{DEPLOY_ID}/static/downloads/*.apk && '
    f'ls -lh /home/ubuntu/{DEPLOY_ID}/static/downloads/*.apk'
)

u3 = f"https://{DOMAIN}/autodev/{DEPLOY_ID}/downloads/{APK}"
u4 = f"https://{DOMAIN}/autodev/{DEPLOY_ID}/downloads/bini_health_android_latest.apk"

for u in [u1, u2, u3, u4]:
    # full GET with -o /tmp/apk.test, then stat
    run(
        f'curl -sS -L -o /tmp/apk_verify.bin -w "HTTP %{{http_code}} size=%{{size_download}} time=%{{time_total}}s content_type=%{{content_type}}\\n" "{u}" && '
        f'stat -c "downloaded bytes=%s" /tmp/apk_verify.bin && '
        f'file /tmp/apk_verify.bin | head -1'
    )

c.close()
