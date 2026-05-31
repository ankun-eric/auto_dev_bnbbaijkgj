#!/usr/bin/env python3
"""[PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31 修复版] 打包小程序 zip 并上传到 gateway-nginx 静态目录"""
import os, time, random, zipfile, paramiko
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "miniprogram"
HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PWD = "Newbang888"
PID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{PID}"
GW = "gateway-nginx"

ts = time.strftime("%Y%m%d_%H%M%S"); rnd = "%04x" % random.randint(0, 0xFFFF)
fname = f"miniprogram_invite_bugfix_{ts}_{rnd}.zip"
out = ROOT / fname

print(f"[1/4] 打包 {SRC} -> {fname}")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__")]
        for f in files:
            if f.endswith(".log"):
                continue
            p = Path(root) / f
            zf.write(p, p.relative_to(SRC.parent))
size_mb = out.stat().st_size / 1024 / 1024
print(f"   zip 大小: {size_mb:.2f} MB")

ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=30, look_for_keys=False, allow_agent=False)
def run(cmd, t=300):
    i, o, e = ssh.exec_command(cmd, timeout=t)
    return o.read().decode("utf-8", "ignore"), e.read().decode("utf-8", "ignore")

print("[2/4] 上传并放入 gateway-nginx /data/static/apk/")
remote_tmp = f"/tmp/{fname}"
sftp = ssh.open_sftp(); sftp.put(str(out), remote_tmp); sftp.close()
run(f"docker exec {GW} mkdir -p /data/static/apk")
run(f"docker cp {remote_tmp} {GW}:/data/static/apk/{fname}")
run(f"rm -f {remote_tmp}")

print("[3/4] 验证下载链接")
url = f"{BASE_URL}/apk/{fname}"
o, _ = run(f"curl -s -o /dev/null -w '%{{http_code}}' {url}")
print(f"   HTTP={o.strip()}  {url}")

with open(ROOT / "_mp_invite_bugfix_url.txt", "w", encoding="utf-8") as f:
    f.write(url)
ssh.close()
print(f"[4/4] DONE -> {url}")
