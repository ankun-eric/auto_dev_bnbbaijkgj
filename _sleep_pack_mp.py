#!/usr/bin/env python3
"""[PRD-SLEEP-ALIGN-BP-V1] 打包小程序并上传到 gateway downloads/ 目录"""
import os, shutil, tempfile, time, secrets
import paramiko

HOST, PORT, USER, PWD = "newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def run(c, cmd, t=120, ign=False):
    print(f"\n$ {cmd[:200]}", flush=True)
    _, so, se = c.exec_command(cmd, timeout=t + 60)
    out = so.read().decode("utf-8", "replace"); err = se.read().decode("utf-8", "replace")
    rc = so.channel.recv_exit_status()
    if out.strip(): print(out[-2000:])
    if err.strip(): print("STDERR:", err[-800:])
    if rc != 0 and not ign: raise RuntimeError(f"rc={rc}: {cmd[:80]}")
    return rc, out


def main():
    base = os.path.abspath(os.path.dirname(__file__))
    src = os.path.join(base, "miniprogram")
    ts = time.strftime("%Y%m%d_%H%M%S"); rand = secrets.token_hex(2)
    fn = f"miniprogram_sleep_align_{ts}_{rand}.zip"
    out_path = os.path.join(base, fn)
    tmp = tempfile.mkdtemp(prefix="mp_sleep_")
    try:
        shutil.copytree(src, os.path.join(tmp, "miniprogram"), ignore=shutil.ignore_patterns(
            "node_modules", ".git", "miniprogram_npm", "__pycache__", "*.pyc", ".DS_Store"))
        shutil.make_archive(out_path[:-4], "zip", tmp, "miniprogram")
        print(f"Zip {fn} = {os.path.getsize(out_path)/1024:.1f} KB")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30, allow_agent=False, look_for_keys=False)
    try:
        tmp_remote = f"/home/ubuntu/{fn}"
        sftp = c.open_sftp(); sftp.put(out_path, tmp_remote); sftp.close()
        run(c, f"docker cp {tmp_remote} gateway-nginx:/data/static/apk/{fn}")
        run(c, f"docker exec gateway-nginx ls -l /data/static/apk/{fn}")
        url = f"{BASE_URL}/downloads/{fn}"
        rc, out = run(c, f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}'", ign=True)
        code = out.strip()
        print(f"\nDONE filename: {fn}\nDONE URL: {url}\nDONE HTTP: {code}")
        run(c, f"rm -f {tmp_remote}", ign=True)
        with open(os.path.join(base, "_mp_sleep_align_url.txt"), "w") as f:
            f.write(f"{fn}\n{url}\nHTTP={code}\n")
    finally:
        c.close()


if __name__ == "__main__":
    main()
