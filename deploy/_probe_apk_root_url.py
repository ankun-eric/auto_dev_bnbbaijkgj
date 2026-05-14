"""Probe how root-level apk URLs and uploads/static are served."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(cmd):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=20,
              look_for_keys=False, allow_agent=False)
    try:
        _, o, e = c.exec_command(cmd, timeout=60)
        return o.read().decode("utf-8", "ignore"), e.read().decode("utf-8", "ignore")
    finally:
        c.close()


B = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
cmds = [
    # show full conf for this deploy id
    f"docker exec gateway cat /etc/nginx/conf.d/{DEPLOY_ID}.conf",
    # test the existing root-level apk file (app_prd440 exists in uploads/)
    f"curl -Is '{B}/app_prd440_20260510014236_5145.apk' | head -5",
    # the same file under /uploads/
    f"curl -Is '{B}/uploads/app_prd440_20260510014236_5145.apk' | head -5",
    # one of the existing apks in static/apk/
    f"curl -Is '{B}/apk/app_pointsskin_20260514_180959_434b.apk' | head -5",
    # test a known miniprogram zip in /uploads/static/
    f"curl -Is '{B}/uploads/static/miniprogram_promptcfg_20260514_222143_d65c.zip' | head -5",
]
for c in cmds:
    print("\n$ " + c)
    out, err = run(c)
    print(out)
    if err.strip():
        print("[ERR]", err)
