"""UI Polish - 打包微信小程序 zip 并上传到服务器 static/downloads 目录。

产出物 URL 格式：
  https://newbb.test.bangbangvip.com/autodev/<DEPLOY_ID>/<zip_name>.zip
（直接挂在项目基础 URL 根下，不带 /downloads/ 或 /static/downloads/ 前缀）

若上述直连 URL 因 nginx H5 catch-all 返回 404/非 zip，则自动向 gateway nginx 注入
一个正则 location，把 `^/autodev/<DEPLOY_ID>/[^/]+\.zip$` 别名到容器内
`/data/static/downloads/`，然后 reload 并重试。
"""

import base64
import datetime
import fnmatch
import json
import os
import secrets
import sys
import time
import traceback
import urllib.error
import urllib.request
import zipfile

import paramiko


# --------------------------- Constants ---------------------------
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
DOMAIN = "newbb.test.bangbangvip.com"
BASE_URL = f"https://{DOMAIN}/autodev/{DEPLOY_ID}"

PROJECT_DIR_REMOTE = f"/home/ubuntu/{DEPLOY_ID}"
STATIC_DOWNLOADS_REMOTE = f"{PROJECT_DIR_REMOTE}/static/downloads"

HOST_NGINX_CONF = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
GATEWAY_CONTAINER = "gateway"

MP_LOCAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "miniprogram"
)

SKIP_DIRS = {"node_modules", ".git", "dist", "miniprogram_npm", "__pycache__"}
SKIP_FILES_EXACT = {".DS_Store", "Thumbs.db"}
SKIP_FILE_PATTERNS = ["*.log", "*.tmp"]

MIN_SIZE_BYTES = 10 * 1024  # 10KB minimum


# --------------------------- SSH helpers ---------------------------
def ssh_connect(retries=4, backoff=8):
    last = None
    for i in range(retries):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(
                HOST,
                username=SSH_USER,
                password=SSH_PASS,
                timeout=30,
                banner_timeout=30,
                auth_timeout=30,
            )
            return c
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[ssh] connect attempt {i+1}/{retries} failed: {e}; retry in {backoff}s")
            time.sleep(backoff)
    raise last


def run(c, cmd, timeout=180, check=False):
    print(f"$ {cmd[:220]}")
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        tail = out[-1400:]
        print(tail)
    if err.strip():
        print(f"[stderr] {err[-600:]}")
    print(f"[exit {code}]")
    if check and code != 0:
        raise RuntimeError(f"cmd failed rc={code}: {cmd}")
    return code, out, err


# --------------------------- Packaging ---------------------------
def should_skip_file(fn):
    if fn in SKIP_FILES_EXACT:
        return True
    for p in SKIP_FILE_PATTERNS:
        if fnmatch.fnmatch(fn, p):
            return True
    return False


def build_mp_zip(mp_dir, out_path):
    count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(mp_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in files:
                if should_skip_file(fn):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, mp_dir)
                zf.write(full, arcname=rel.replace(os.sep, "/"))
                count += 1
    size = os.path.getsize(out_path)
    print(f"[pack] {count} files -> {out_path} ({size} bytes, {size/1024/1024:.2f} MB)")
    return count, size


def verify_zip_root(zip_path):
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
    must = ["app.json", "project.config.json", "app.js", "app.wxss"]
    for m in must:
        if m not in names:
            raise RuntimeError(f"zip root missing required file: {m}")
    print(f"[verify-zip] root contains app.json/project.config.json/app.js/app.wxss (total {len(names)} entries)")


# --------------------------- HTTP verify ---------------------------
def http_head(url, timeout=25):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "mp-packager/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers) if e.headers else {}
    except Exception as e:  # noqa: BLE001
        return f"ERR:{e}", {}


def check_zip_url(url):
    """返回 (ok:bool, status, content_length:int|None, content_type:str|None, reason:str)。

    判定 ok：HTTP 200 且 Content-Length > MIN_SIZE_BYTES 且 Content-Type 为 zip/octet-stream。
    """
    status, headers = http_head(url)
    cl_raw = headers.get("Content-Length") or headers.get("content-length")
    ctype = headers.get("Content-Type") or headers.get("content-type") or ""
    try:
        cl = int(cl_raw) if cl_raw is not None else None
    except Exception:  # noqa: BLE001
        cl = None

    if status != 200:
        return False, status, cl, ctype, f"status={status}"
    if cl is None or cl <= MIN_SIZE_BYTES:
        return False, status, cl, ctype, f"content-length too small ({cl})"
    ctype_l = (ctype or "").lower()
    # 如果被 H5 next 服务器接管，通常返回 text/html
    if "zip" not in ctype_l and "octet-stream" not in ctype_l:
        return False, status, cl, ctype, f"unexpected content-type={ctype}"
    return True, status, cl, ctype, "ok"


# --------------------------- Nginx fix ---------------------------
NGINX_LOCATION_MARKER = f"# AUTO: direct zip alias for /autodev/{DEPLOY_ID}/*.zip"

NGINX_LOCATION_BLOCK = f"""

{NGINX_LOCATION_MARKER}
location ~ ^/autodev/{DEPLOY_ID}/([^/]+\\.zip)$ {{
    alias /data/static/downloads/$1;
    autoindex off;
    add_header Content-Disposition "attachment";
    types {{
        application/zip zip;
    }}
    default_type application/zip;
}}
"""


def ensure_nginx_direct_zip_location(c):
    """确保 gateway nginx 中存在一个匹配 /autodev/{DEPLOY_ID}/*.zip 的正则 location。"""
    code, conf, _ = run(c, f"cat {HOST_NGINX_CONF}")
    if code != 0:
        raise RuntimeError(f"read nginx conf failed: {HOST_NGINX_CONF}")

    if NGINX_LOCATION_MARKER in conf:
        print("[nginx] direct zip location already present, skip")
        return False

    new_conf = conf.rstrip() + NGINX_LOCATION_BLOCK + "\n"
    ts = time.strftime("%Y%m%d%H%M%S")
    run(c, f"cp {HOST_NGINX_CONF} {HOST_NGINX_CONF}.bak.directzip.{ts}", check=True)

    b64 = base64.b64encode(new_conf.encode("utf-8")).decode("ascii")
    run(c, f"echo {b64} | base64 -d > {HOST_NGINX_CONF}", check=True)

    code, _, _ = run(c, f"docker exec {GATEWAY_CONTAINER} nginx -t")
    if code != 0:
        print("[nginx] config test failed, rolling back")
        run(c, f"cp {HOST_NGINX_CONF}.bak.directzip.{ts} {HOST_NGINX_CONF}")
        raise RuntimeError("nginx -t failed after adding direct zip location")
    run(c, f"docker exec {GATEWAY_CONTAINER} nginx -s reload", check=True)
    print("[nginx] direct zip location added and reloaded")
    return True


# --------------------------- Main ---------------------------
def main():
    result = {
        "zip_name": None,
        "url": None,
        "size_bytes": None,
        "http_status": None,
        "content_length": None,
        "content_type": None,
        "ok": False,
        "error": None,
    }
    try:
        if not os.path.isfile(os.path.join(MP_LOCAL_DIR, "app.json")):
            raise RuntimeError(f"miniprogram/app.json missing in {MP_LOCAL_DIR}")

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rand4 = secrets.token_hex(2)
        zip_name = f"miniprogram_{ts}_{rand4}.zip"
        result["zip_name"] = zip_name

        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_zip = os.path.join(script_dir, zip_name)

        print("=" * 60)
        print(f"[1/4] Packing miniprogram -> {zip_name}")
        print("=" * 60)
        _, size = build_mp_zip(MP_LOCAL_DIR, local_zip)
        result["size_bytes"] = size
        verify_zip_root(local_zip)

        print("\n" + "=" * 60)
        print("[2/4] Uploading via SFTP")
        print("=" * 60)
        c = ssh_connect()
        try:
            run(c, f"mkdir -p {STATIC_DOWNLOADS_REMOTE}", check=True)
            sftp = c.open_sftp()
            remote_zip = f"{STATIC_DOWNLOADS_REMOTE}/{zip_name}"
            print(f"sftp put {local_zip} -> {remote_zip}")
            sftp.put(local_zip, remote_zip)
            sftp.close()
            run(c, f"chmod 644 {remote_zip}")
            run(c, f"ls -lh {remote_zip}")

            url = f"{BASE_URL}/{zip_name}"
            result["url"] = url

            print("\n" + "=" * 60)
            print("[3/4] Verifying URL (direct under project root)")
            print("=" * 60)
            print(f"GET HEAD {url}")
            ok, status, cl, ctype, reason = check_zip_url(url)
            result["http_status"] = status
            result["content_length"] = cl
            result["content_type"] = ctype
            print(f"  status={status} content-length={cl} content-type={ctype} -> {reason}")

            if not ok:
                print("\n" + "=" * 60)
                print("[3.5/4] Direct URL not serving the zip, patching nginx")
                print("=" * 60)
                ensure_nginx_direct_zip_location(c)
                # 小等 reload 生效
                time.sleep(2)
                print(f"[retry] HEAD {url}")
                ok, status, cl, ctype, reason = check_zip_url(url)
                result["http_status"] = status
                result["content_length"] = cl
                result["content_type"] = ctype
                print(f"  status={status} content-length={cl} content-type={ctype} -> {reason}")

            print("\n" + "=" * 60)
            print("[4/4] Final result")
            print("=" * 60)
            result["ok"] = ok
            if not ok:
                result["error"] = reason
        finally:
            c.close()
            try:
                os.remove(local_zip)
            except OSError:
                pass

    except Exception as e:  # noqa: BLE001
        result["error"] = f"{e}\n{traceback.format_exc()}"
        result["ok"] = False

    print("\n" + "#" * 60)
    print("# RESULT JSON")
    print("#" * 60)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 3)


if __name__ == "__main__":
    main()
