"""打包小程序 zip 并上传服务器"""
import os
import sys
import time
import random
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "miniprogram"
HOST = "ubuntu@newbb.test.bangbangvip.com"
REMOTE_DIR = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/miniprogram"
BASE_URL = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"


def main():
    ts = time.strftime("%Y%m%d_%H%M%S")
    rnd = "%04x" % random.randint(0, 0xFFFF)
    fname = f"miniprogram_carev1_{ts}_{rnd}.zip"
    out = ROOT / fname

    print(f"[1/3] 打包 {SRC} -> {out}")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(SRC):
            # 排除无用目录
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__")]
            for f in files:
                if f.endswith((".log",)):
                    continue
                p = Path(root) / f
                arc = p.relative_to(SRC.parent)
                zf.write(p, arc)
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"   zip 大小: {size_mb:.2f} MB")

    print(f"[2/3] 上传到服务器")
    # 确保目录存在
    subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", HOST, f"mkdir -p {REMOTE_DIR}"],
        check=True,
    )
    subprocess.run(
        ["scp", "-o", "StrictHostKeyChecking=no", str(out), f"{HOST}:{REMOTE_DIR}/{fname}"],
        check=True,
    )

    url = f"{BASE_URL}/miniprogram/{fname}"
    print(f"[3/3] 验证下载链接: {url}")
    r = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", HOST,
         f"curl -s -o /dev/null -w '%{{http_code}}' {url}"],
        check=False, capture_output=True, text=True
    )
    print(f"  HTTP code: {r.stdout.strip()}")
    if r.stdout.strip() != "200":
        # 可能 nginx 静态目录路径不对，尝试 downloads
        url2 = f"{BASE_URL}/downloads/{fname}"
        r2 = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", HOST,
             f"sudo cp /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram_static/{fname} /tmp/ 2>/dev/null; docker exec gateway curl -s -o /dev/null -w '%{{http_code}}' http://localhost//miniprogram/{fname}"],
            capture_output=True, text=True
        )
        print(f"  尝试 gateway 内部: {r2.stdout.strip()}")

    # 保存结果
    with open("_mp_carev1_url.txt", "w") as f:
        f.write(url)
    print(f"\nDONE: {url}")


if __name__ == "__main__":
    main()
