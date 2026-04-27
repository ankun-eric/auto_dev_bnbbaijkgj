#!/usr/bin/env python3
"""部署 v1.5 验证码视觉规格（v2：增加 ssh 命令超时 + git 重试）

变化：
- ssh_exec 超时 1800s
- git fetch 单次超时 1500s 且最多重试 8 次
- 探针使用 docker exec ... bash -lc 改善兼容
"""
from __future__ import annotations

import base64
import re
import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_MSG = ROOT / "deploy" / "deploy_msg.txt"


def _parse_deploy_msg() -> dict:
    text = DEPLOY_MSG.read_text(encoding="utf-8")
    info: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            k, _, v = line.partition(":")
            info[k.strip()] = v.strip()
    return info


_INFO = _parse_deploy_msg()
HOST = _INFO["服务器域名/IP"]
PORT = int(_INFO.get("SSH端口", "22"))
USER = _INFO["SSH用户名"]
PWD = _INFO["SSH密码"]
DEPLOY_ID = _INFO["DEPLOY_ID"]
BASE_URL = _INFO["项目基础URL"]

GIT_REPO = _INFO.get("Git仓库链接", "")
GIT_USER = _INFO.get("Git用户名", "")
GIT_TOKEN = _INFO.get("Git访问token", "")


def ssh_exec(client: paramiko.SSHClient, cmd: str, timeout: int = 1800) -> tuple[int, str, str]:
    print(f"\n$ {cmd[:300]}{'...' if len(cmd)>300 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    try:
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
    except Exception as e:
        print(f"[ssh_exec exception] {e}")
        return -1, "", str(e)
    if out.strip():
        print(out)
    if err.strip():
        print("[stderr]", err)
    print(f"[exit] {rc}")
    return rc, out, err


def main() -> int:
    print(f"=== Deploy v1.5 captcha visual upgrade (v2) ===")
    print(f"host       : {HOST}")
    print(f"DEPLOY_ID  : {DEPLOY_ID}")
    print(f"base URL   : {BASE_URL}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, port=PORT, username=USER, password=PWD, timeout=30,
                   banner_timeout=30, auth_timeout=30)
    transport = client.get_transport()
    if transport:
        transport.set_keepalive(15)

    proj_dir = f"/home/ubuntu/{DEPLOY_ID}"

    rc, out, _ = ssh_exec(client, f"ls -la {proj_dir}/.git 2>/dev/null && echo OK || echo NOTFOUND")
    if "NOTFOUND" in out:
        print(f"[ERROR] 服务器上未找到项目目录 {proj_dir}/.git")
        return 2

    # set git remote with token
    m = re.match(r"https://(.+?)/(.+?)/(.+)", GIT_REPO.rstrip("/"))
    if m:
        host_part, owner, repo = m.group(1), m.group(2), m.group(3)
        if not repo.endswith(".git"):
            repo += ".git"
        auth_url = f"https://{GIT_USER}:{GIT_TOKEN}@{host_part}/{owner}/{repo}"
        ssh_exec(client, f"cd {proj_dir} && git remote set-url origin {auth_url}")

    # git fetch with retries on server side (also our own outer retries)
    fetch_ok = False
    for attempt in range(1, 9):
        rc, out, err = ssh_exec(
            client,
            f"cd {proj_dir} && timeout 600 git -c http.postBuffer=524288000 -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=60 fetch --depth=1 origin master 2>&1 && git reset --hard FETCH_HEAD && git clean -fd -e '*.log' -e '_deploy_tmp/'",
            timeout=900,
        )
        if rc == 0:
            fetch_ok = True
            break
        print(f"[WARN] git fetch 第 {attempt} 次失败 (rc={rc})，等待 8s 后重试...")
        time.sleep(8)
    if not fetch_ok:
        print("[ERROR] git fetch/reset 多次失败")
        return 3

    ssh_exec(client, f"cd {proj_dir} && git log -1 --oneline")
    ssh_exec(client, f"cd {proj_dir} && head -25 backend/app/services/captcha_service.py")

    backend_container = f"{DEPLOY_ID}-backend"

    rc, out, _ = ssh_exec(client, f"ls {proj_dir}/docker-compose.prod.yml 2>/dev/null && echo HAVE_PROD || echo NO_PROD")
    compose_file = "docker-compose.prod.yml" if "HAVE_PROD" in out else "docker-compose.yml"
    print(f"使用 compose 文件: {compose_file}")

    rc, _, _ = ssh_exec(
        client,
        f"cd {proj_dir} && docker compose -f {compose_file} build --no-cache backend 2>&1 | tail -80",
        timeout=1500,
    )
    if rc != 0:
        print("[ERROR] backend 镜像构建失败")
        return 4
    rc, _, _ = ssh_exec(
        client,
        f"cd {proj_dir} && docker compose -f {compose_file} up -d backend 2>&1 | tail -30",
        timeout=300,
    )
    if rc != 0:
        print("[ERROR] backend 容器启动失败")
        return 5

    # 等待健康
    print("\n等待 backend 健康...")
    for i in range(36):
        rc, out, _ = ssh_exec(
            client,
            f"docker inspect --format='{{{{.State.Health.Status}}}}' {backend_container} 2>/dev/null || docker inspect --format='{{{{.State.Status}}}}' {backend_container}",
        )
        st = out.strip().splitlines()[-1] if out.strip() else ""
        if st == "healthy":
            print(f"[OK] backend healthy after {(i+1)*5}s")
            break
        if st == "running" and i > 6:
            # 如果没有 healthcheck 也接受 running
            print(f"[INFO] backend running (no healthcheck) after {(i+1)*5}s")
            break
        time.sleep(5)
    ssh_exec(client, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

    # gateway 重新连接网络
    network_name = f"{DEPLOY_ID}-network"
    rc, out, _ = ssh_exec(client, "docker ps --filter name=gateway --format '{{.Names}}' | head -n1")
    gw = out.strip().splitlines()[0] if out.strip() else ""
    if gw:
        ssh_exec(client, f"docker network connect {network_name} {gw} 2>/dev/null || true")
        ssh_exec(client, f"docker exec {gw} nginx -s reload 2>&1 | head -5")
    else:
        print("[WARN] 未找到 gateway 容器，跳过网络重连")

    # 容器内 PNG 探针
    print("\n=== v1.5 PNG 探针：字号=48 + 物理像素 160×60 + 字节数合理 ===")
    py_script = (
        "import colorsys, io\n"
        "from app.services.captcha_service import (\n"
        "    IMG_WIDTH, IMG_HEIGHT, FONT_SIZE,\n"
        "    render_captcha_png, _random_dark_color, _random_light_color\n"
        ")\n"
        "from PIL import Image\n"
        "sizes = []\n"
        "img0 = None\n"
        "for _ in range(20):\n"
        "    p = render_captcha_png('AB23')\n"
        "    sizes.append(len(p))\n"
        "    if img0 is None:\n"
        "        img0 = Image.open(io.BytesIO(p)); img0.load()\n"
        "print('PNG_PHYSICAL=' + str(img0.size))\n"
        "print('CONST=%dx%d' % (IMG_WIDTH, IMG_HEIGHT))\n"
        "print('FONT_SIZE=' + str(FONT_SIZE))\n"
        "print('AVG_BYTES=%d MAX_BYTES=%d MIN_BYTES=%d' % (sum(sizes)//len(sizes), max(sizes), min(sizes)))\n"
        "ls = []\n"
        "for _ in range(50):\n"
        "    r,g,b = _random_dark_color()\n"
        "    _,l,_ = colorsys.rgb_to_hls(r/255, g/255, b/255)\n"
        "    ls.append(l)\n"
        "print('DARK_L_AVG=%.3f MIN=%.3f MAX=%.3f' % (sum(ls)/len(ls), min(ls), max(ls)))\n"
        "ll = []\n"
        "for _ in range(50):\n"
        "    r,g,b = _random_light_color(0.70)\n"
        "    _,l,_ = colorsys.rgb_to_hls(r/255, g/255, b/255)\n"
        "    ll.append(l)\n"
        "print('LIGHT_L_AVG=%.3f MIN=%.3f' % (sum(ll)/len(ll), min(ll)))\n"
        "ok = (img0.size==(160,60) and IMG_WIDTH==160 and IMG_HEIGHT==60 and FONT_SIZE==48)\n"
        "print('V15_PROBE_OK=' + str(ok))\n"
    )
    enc = base64.b64encode(py_script.encode("utf-8")).decode("ascii")
    rc, probe_out, _ = ssh_exec(
        client,
        f"docker exec {backend_container} sh -c 'echo {enc} | base64 -d | python'",
    )
    probe_ok = "V15_PROBE_OK=True" in probe_out

    # 验证关键链接
    print("\n=== 验证关键链接 ===")
    test_urls = [
        f"{BASE_URL}/api/health",
        f"{BASE_URL}/api/captcha/image",
        f"{BASE_URL}/login",
        f"{BASE_URL}/merchant/login",
        f"{BASE_URL}/merchant/m/login",
        f"{BASE_URL}/",
    ]
    summary = []
    for url in test_urls:
        rc, out, _ = ssh_exec(client, f"curl -k -s -o /dev/null -w '%{{http_code}}' '{url}'")
        code = out.strip().splitlines()[-1] if out.strip() else ""
        ok = code in ("200", "204", "301", "302", "307", "308")
        if "/api/captcha/image" in url:
            ok = code == "200"
        summary.append((url, code, "OK" if ok else "FAIL"))

    print("\n=== 链接检查结果 ===")
    for u, c, s in summary:
        print(f"  [{s:4}] {c}  {u}")

    failed = [s for s in summary if s[2] == "FAIL"]
    captcha_ok = all(s[2] == "OK" for s in summary if "/api/captcha/image" in s[0])

    print("\n=== 总结 ===")
    print(f"  V1.5 PNG 探针: {'PASS' if probe_ok else 'FAIL'}")
    print(f"  /api/captcha/image: {'PASS' if captcha_ok else 'FAIL'}")
    print(f"  其他链接失败: {len(failed)}")

    if not probe_ok or not captcha_ok:
        return 6

    print("\n=== 部署成功 v1.5 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
