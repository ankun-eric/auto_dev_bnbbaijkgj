#!/usr/bin/env python3
"""部署 captcha 字号 v1.3 - 修复版（自动发现 gateway 容器名 + 等后端就绪 + 308 视为成功）。

仅做后置任务：
- 查找正确的 gateway 容器名（autodev-gateway / gateway-nginx / nginx-gateway 等）
- 等后端 healthy 后再抓 captcha PNG，校验物理像素
- 关键页面可达性检查（308 视为成功）
"""
import io
import os
import sys
import time
import paramiko
import requests
from datetime import datetime

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", ".chat_output", "v13_retry")
OUT_DIR = os.path.abspath(OUT_DIR)
os.makedirs(OUT_DIR, exist_ok=True)
LOG_PATH = os.path.join(OUT_DIR, f"deploy_v13_retry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def ssh_exec(cli, cmd, timeout=300):
    log(f"$ {cmd}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        log(out.rstrip())
    if err.strip():
        log("[stderr] " + err.rstrip())
    log(f"# exit={rc}")
    return rc, out, err


def main():
    log("=" * 70)
    log("captcha v1.3 部署后置校验")
    log(f"目标: {BASE_URL}")
    log("=" * 70)

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, PORT, USER, PWD, timeout=30)

    try:
        # 1. 找到 gateway 容器名（包含 nginx 或 gateway，且不是项目容器）
        rc, out, _ = ssh_exec(
            cli,
            "docker ps --format '{{.Names}}|{{.Image}}' | grep -Ei 'nginx|gateway|traefik' || true",
        )
        gw_candidates = []
        for ln in out.splitlines():
            name = ln.split("|", 1)[0].strip()
            if not name or DEPLOY_ID in name:
                continue
            gw_candidates.append(name)
        log(f"候选 gateway 容器: {gw_candidates}")
        gw_name = gw_candidates[0] if gw_candidates else None

        if gw_name:
            ssh_exec(cli, f"docker network connect {DEPLOY_ID}-network {gw_name} 2>&1 || true")
            ssh_exec(cli, f"docker exec {gw_name} nginx -t && docker exec {gw_name} nginx -s reload || true")
        else:
            log("⚠️ 未找到 gateway 容器，跳过 reload（可能 traefik 自动发现）")

        # 2. 等后端就绪（最多 60 秒）
        log("等待 backend 接口就绪 ...")
        ok = False
        for i in range(20):
            try:
                r = requests.get(f"{BASE_URL}/api/health", timeout=8)
                if r.status_code == 200:
                    log(f"  /api/health -> 200，后端已就绪")
                    ok = True
                    break
            except Exception:
                pass
            time.sleep(3)
        if not ok:
            log("⚠️ 后端 60 秒内仍未就绪，继续后续校验")

        # 3. 抓 captcha PNG 校验
        log("抓取真实验证码 PNG 并校验物理像素 ...")
        captcha_url = f"{BASE_URL}/api/captcha/image"
        captcha_ok = False
        png_size = None
        for attempt in range(5):
            try:
                r = requests.get(captcha_url, timeout=15)
                log(f"GET {captcha_url} -> {r.status_code} ({len(r.content)} bytes, {r.headers.get('content-type')})")
                if r.status_code == 200 and "image" in (r.headers.get("content-type") or ""):
                    png_path = os.path.join(OUT_DIR, "captcha_real_v13.png")
                    with open(png_path, "wb") as f:
                        f.write(r.content)
                    from PIL import Image
                    img = Image.open(io.BytesIO(r.content))
                    png_size = img.size
                    log(f"  PNG 物理像素 = {png_size}（期望 320×120）")
                    log(f"  PNG 体积 = {len(r.content)} bytes")
                    log(f"  PNG 已保存: {png_path}")
                    if png_size == (320, 120):
                        captcha_ok = True
                    break
            except Exception as e:
                log(f"  尝试 {attempt+1} 失败: {e}")
            time.sleep(3)

        # 4. 关键页面可达性检查（200 / 301 / 302 / 304 / 308 均视为成功）
        log("=" * 70)
        log("关键页面可达性检查（200/301/302/304/308 视为成功）")
        log("=" * 70)
        urls = [
            f"{BASE_URL}/",
            f"{BASE_URL}/admin/login",
            f"{BASE_URL}/admin/login/",
            f"{BASE_URL}/merchant/login",
            f"{BASE_URL}/merchant/login/",
            f"{BASE_URL}/merchant/m/",
            f"{BASE_URL}/api/health",
            f"{BASE_URL}/api/captcha/image",
        ]
        results = []
        for u in urls:
            try:
                r = requests.get(u, timeout=15, allow_redirects=False)
                ok = r.status_code in (200, 301, 302, 304, 307, 308)
                results.append((u, r.status_code, ok))
                log(f"  {'✅' if ok else '❌'} {r.status_code}  {u}")
            except Exception as e:
                results.append((u, "ERR", False))
                log(f"  ❌ ERR  {u}  ({e})")

        unreachable = [r for r in results if not r[2]]
        log("=" * 70)
        log(f"PNG 物理尺寸校验: {'✅ 通过' if captcha_ok else '❌ 失败'} ({png_size})")
        log(f"链接可达性: {'✅ 全部通过' if not unreachable else f'❌ {len(unreachable)} 个不可达'}")
        return 0 if (captcha_ok and not unreachable) else 1

    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
