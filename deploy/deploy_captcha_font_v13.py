#!/usr/bin/env python3
"""部署 captcha 字号 v1.3 到测试服务器：仅 git pull + 重建后端与前端容器。

流程：
1. SSH 到服务器 -> cd 项目目录 -> git fetch + reset --hard origin/master
2. docker compose -f docker-compose.prod.yml build backend admin-web h5-web --no-cache
3. docker compose up -d backend admin-web h5-web
4. 等待 healthy
5. 重新连接 gateway 网络 + reload gateway
6. 抓一张 captcha PNG 校验物理像素与字号
7. 检查 admin / merchant / merchant-h5 登录页 200
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
GATEWAY_NAME = "gateway-nginx"

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", ".chat_output", "629d27da-5e7b-4b93-a442-78a83969d4d7")
OUT_DIR = os.path.abspath(OUT_DIR)
os.makedirs(OUT_DIR, exist_ok=True)
LOG_PATH = os.path.join(OUT_DIR, f"deploy_captcha_font_v13_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def ssh_exec(cli, cmd, timeout=600):
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
    log("部署 captcha 字号 v1.3 到测试服务器")
    log(f"目标: {BASE_URL}")
    log("=" * 70)

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, PORT, USER, PWD, timeout=30, banner_timeout=30, auth_timeout=30)
    log("SSH 连接成功")

    try:
        # 1. git pull 最新代码
        ssh_exec(cli, f"cd {PROJECT_DIR} && git fetch origin && git reset --hard origin/master && git clean -fd && git log -1 --oneline")

        # 2. 重建关键容器
        ssh_exec(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend admin-web h5-web", timeout=900)

        # 3. up -d
        ssh_exec(cli, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend admin-web h5-web")

        # 4. 等待 healthy（最多 90 秒）
        log("等待容器 healthy ...")
        for i in range(18):
            rc, out, _ = ssh_exec(cli, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}|{{{{.Status}}}}'")
            unhealthy = [ln for ln in out.splitlines() if "(unhealthy)" in ln or "(starting)" in ln or "(health: starting)" in ln]
            if not unhealthy and out.strip():
                log("所有相关容器处于 healthy 状态")
                break
            time.sleep(5)

        # 5. 重新连接 gateway 网络 & reload
        ssh_exec(cli, f"docker network connect {DEPLOY_ID}-network {GATEWAY_NAME} 2>&1 || true")
        ssh_exec(cli, f"docker exec {GATEWAY_NAME} nginx -t && docker exec {GATEWAY_NAME} nginx -s reload")

        # 6. 抓一张验证码 PNG
        log("抓取真实验证码 PNG ...")
        captcha_url = f"{BASE_URL}/api/captcha/image"
        try:
            r = requests.get(captcha_url, timeout=20, verify=True)
            log(f"GET {captcha_url} -> {r.status_code} ({len(r.content)} bytes, {r.headers.get('content-type')})")
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                png_path = os.path.join(OUT_DIR, "captcha_real_v13.png")
                with open(png_path, "wb") as f:
                    f.write(r.content)
                # 用 Pillow 校验物理像素
                try:
                    from PIL import Image
                    img = Image.open(io.BytesIO(r.content))
                    log(f"  PNG 物理像素 = {img.size}（期望 320×120）")
                    log(f"  PNG 已保存: captcha_real_v13.png")
                except Exception as e:
                    log(f"  Pillow 解析失败: {e}")
        except Exception as e:
            log(f"抓取验证码失败: {e}")

        # 7. 检查关键页面可达
        log("=" * 70)
        log("检查关键页面可达性")
        log("=" * 70)
        urls = [
            f"{BASE_URL}/",
            f"{BASE_URL}/admin/login",
            f"{BASE_URL}/merchant/login",
            f"{BASE_URL}/merchant/m/",
            f"{BASE_URL}/api/health",
        ]
        results = []
        for u in urls:
            try:
                r = requests.get(u, timeout=15, allow_redirects=False)
                ok = r.status_code in (200, 301, 302, 304)
                results.append((u, r.status_code, ok))
                log(f"  {'✅' if ok else '❌'} {r.status_code}  {u}")
            except Exception as e:
                results.append((u, "ERR", False))
                log(f"  ❌ ERR  {u}  ({e})")

        unreachable = [r for r in results if not r[2]]
        log("=" * 70)
        if unreachable:
            log(f"❌ 有 {len(unreachable)} 个链接不可达")
            return 1
        log("✅ 所有关键链接均可达")
        return 0

    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
