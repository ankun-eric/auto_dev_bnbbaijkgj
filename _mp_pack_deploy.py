import os
import time
import secrets
import zipfile
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
GATEWAY = "gateway-nginx"
APK_DIR = "/data/static/apk/"

SRC = r"C:\auto_output\bnbbaijkgj\miniprogram"
EXCLUDE_DIRS = {"node_modules", ".git", "miniprogram_npm"}


def make_zip():
    ts = time.strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)
    name = f"miniprogram_{ts}_{rand}.zip"
    out_path = os.path.join(r"C:\auto_output\bnbbaijkgj", name)
    count = 0
    has_appjson = False
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(SRC):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, SRC).replace("\\", "/")
                if rel == "app.json":
                    has_appjson = True
                zf.write(full, rel)
                count += 1
    assert has_appjson, "app.json not at top level!"
    print(f"[zip] {name} files={count} size={os.path.getsize(out_path)} appjson_top={has_appjson}")
    return name, out_path


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=22, username=USER, password=PWD, timeout=30)
    return c


def retry(fn, what):
    delay = 10
    last = None
    for attempt in range(3):
        try:
            return fn()
        except Exception as e:
            last = e
            print(f"[retry {attempt+1}] {what}: {e}")
            time.sleep(delay)
            delay *= 2
    raise last


def upload_and_deploy(name, local_path):
    remote_tmp = f"/home/ubuntu/{name}"

    def _sftp():
        c = connect()
        sftp = c.open_sftp()
        sftp.put(local_path, remote_tmp)
        sftp.close()
        c.close()
        print(f"[sftp] uploaded -> {remote_tmp}")
    retry(_sftp, "sftp upload")

    def _cp():
        c = connect()
        cmd = (
            f"docker cp {remote_tmp} {GATEWAY}:{APK_DIR}{name} && "
            f"docker exec {GATEWAY} ls -la {APK_DIR}{name} && "
            f"rm -f {remote_tmp}"
        )
        stdin, stdout, stderr = c.exec_command(cmd, timeout=120, get_pty=True)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        c.close()
        print("[docker cp]\n" + out)
        if err.strip():
            print("[docker cp err]\n" + err)
        if name not in out:
            raise RuntimeError("file not found in container after cp")
    retry(_cp, "docker cp")


def verify(name):
    import urllib.request
    url = f"{BASE_URL}/downloads/{name}"

    def _get():
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.getheader("Content-Type"), r.getheader("Content-Length")
    status, ctype, clen = retry(_get, "http verify")
    print(f"[verify] {url} -> {status} type={ctype} len={clen}")
    return url, status


if __name__ == "__main__":
    name, local_path = make_zip()
    upload_and_deploy(name, local_path)
    url, status = verify(name)
    print("\n===== RESULT =====")
    print("FILENAME:", name)
    print("URL:", url)
    print("HTTP_STATUS:", status)
