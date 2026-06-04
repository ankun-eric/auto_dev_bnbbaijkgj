"""SFTP upload changed files for CARE-MODE-OPTIM-V4 to server project dir."""
import os, posixpath, paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
LOCAL_ROOT = r"C:\auto_output\bnbbaijkgj"
REMOTE_ROOT = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

FILES = [
    "backend/app/api/maps.py",
    "backend/app/api/care_card_v1.py",
    "backend/tests/test_care_mode_optim_v4_20260531.py",
    "miniprogram/app.json",
    "miniprogram/pages/ai/index.js",
    "miniprogram/pages/care-ai-home/index.js",
    "miniprogram/pages/care-ai-home/index.wxml",
    "miniprogram/pages/care-ai-home/index.wxss",
    "miniprogram/pages/care-medication/index.js",
    "miniprogram/pages/care-medication/index.json",
    "miniprogram/pages/care-medication/index.wxml",
    "miniprogram/pages/care-medication/index.wxss",
    "miniprogram/pages/care-share-location/index.js",
    "miniprogram/pages/care-share-location/index.json",
    "miniprogram/pages/care-share-location/index.wxml",
    "miniprogram/pages/care-share-location/index.wxss",
    "h5-web/src/app/care-ai-home/sos/page.tsx",
    "h5-web/src/app/care-ai-home/today-health/page.tsx",
    "h5-web/src/app/care-ai-home/share-location/[token]/page.tsx",
]

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)
sftp = cli.open_sftp()


def ensure_remote_dir(remote_dir):
    parts = remote_dir.strip("/").split("/")
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)


for rel in FILES:
    local = os.path.join(LOCAL_ROOT, *rel.split("/"))
    remote = posixpath.join(REMOTE_ROOT, rel)
    ensure_remote_dir(posixpath.dirname(remote))
    sftp.put(local, remote)
    print("uploaded", rel)

sftp.close()
cli.close()
print("ALL DONE")
