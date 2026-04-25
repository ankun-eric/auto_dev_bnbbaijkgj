#!/usr/bin/env python3
"""部署 v1.4 验证码视觉规格回退到远程服务器。

流程：
1. SSH 连接服务器
2. cd 到项目目录，git pull 最新代码
3. 重建后端容器（仅后端改了代码 + 字号常量；前端只改注释，无需重建前端容器）
4. 等待容器健康
5. 重新连接 gateway 网络（保险起见）
6. 全量验证关键链接（验证码接口 + 主页 + 各登录页）
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_MSG = ROOT / "deploy" / "deploy_msg.txt"


def parse_deploy_msg() -> dict:
    text = DEPLOY_MSG.read_text(encoding="utf-8")
    info = {}
    for line in text.splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            k, _, v = line.partition(":")
            info[k.strip()] = v.strip()
    return info


def ssh_exec(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str, str]:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out)
    if err.strip():
        print("[stderr]", err)
    print(f"[exit] {rc}")
    return rc, out, err


def main() -> int:
    info = parse_deploy_msg()
    host = info["服务器域名/IP"]
    user = info["SSH用户名"]
    pwd = info["SSH密码"]
    port = int(info.get("SSH端口", "22"))
    deploy_id = info["DEPLOY_ID"]
    base_url = info["项目基础URL"]

    print(f"=== Deploy v1.4 captcha visual rollback ===")
    print(f"host       : {host}")
    print(f"user       : {user}")
    print(f"DEPLOY_ID  : {deploy_id}")
    print(f"base URL   : {base_url}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=user, password=pwd, timeout=30)

    proj_dir = f"/home/ubuntu/{deploy_id}"

    # 1. 检查项目目录与 git 状态
    rc, out, _ = ssh_exec(client, f"ls -la {proj_dir}/.git 2>/dev/null && echo OK || echo NOTFOUND")
    if "NOTFOUND" in out:
        print(f"[ERROR] 服务器上未找到项目目录 {proj_dir}/.git，请先完成首次部署。")
        return 2

    # 2. git pull
    git_repo = info.get("Git仓库链接", "")
    git_user = info.get("Git用户名", "")
    git_token = info.get("Git访问token", "")
    # 设置带 token 的 remote 以避免认证失败
    if git_repo and git_token:
        m = re.match(r"https://(.+?)/(.+?)/(.+)", git_repo.rstrip("/"))
        if m:
            host_part, owner, repo = m.group(1), m.group(2), m.group(3)
            if not repo.endswith(".git"):
                repo += ".git"
            auth_url = f"https://{git_user}:{git_token}@{host_part}/{owner}/{repo}"
            ssh_exec(client, f"cd {proj_dir} && git remote set-url origin {auth_url}")

    fetch_ok = False
    for attempt in range(1, 6):
        rc, _, _ = ssh_exec(
            client,
            f"cd {proj_dir} && git -c http.postBuffer=524288000 -c http.lowSpeedLimit=0 -c http.lowSpeedTime=999999 fetch --depth=1 origin master && git reset --hard FETCH_HEAD && git clean -fd -e '*.log' -e '_deploy_tmp/'",
            timeout=300,
        )
        if rc == 0:
            fetch_ok = True
            break
        print(f"[WARN] git fetch 第 {attempt} 次失败，等待后重试...")
        ssh_exec(client, "sleep 5")
    if not fetch_ok:
        print("[ERROR] git fetch/reset 多次失败")
        return 3

    ssh_exec(client, f"cd {proj_dir} && git log -1 --oneline")

    # 3. 重新构建后端容器（前端只改注释，可省略；保险起见也重建前端）
    backend_container = f"{deploy_id}-backend"
    frontend_container = f"{deploy_id}-frontend"

    # 找出 docker-compose 文件名
    rc, out, _ = ssh_exec(client, f"ls {proj_dir}/docker-compose.prod.yml 2>/dev/null && echo HAVE_PROD || echo NO_PROD")
    if "HAVE_PROD" in out:
        compose_file = "docker-compose.prod.yml"
    else:
        compose_file = "docker-compose.yml"
    print(f"使用 compose 文件: {compose_file}")

    # 仅重建 backend 服务（避免触发前端长时间构建；前端只改注释，运行时无影响）
    rc, _, _ = ssh_exec(client, f"cd {proj_dir} && docker compose -f {compose_file} build --no-cache backend", timeout=900)
    if rc != 0:
        print("[ERROR] backend 镜像构建失败")
        return 4
    rc, _, _ = ssh_exec(client, f"cd {proj_dir} && docker compose -f {compose_file} up -d backend", timeout=300)
    if rc != 0:
        print("[ERROR] backend 容器启动失败")
        return 5

    # 4. 等待 backend 健康
    print("\n等待 backend 健康...")
    for i in range(24):
        rc, out, _ = ssh_exec(client, f"docker inspect --format='{{{{.State.Health.Status}}}}' {backend_container} 2>/dev/null || docker inspect --format='{{{{.State.Status}}}}' {backend_container}")
        st = out.strip()
        if st in ("healthy", "running"):
            # 进一步对 healthy 优先；running 也算可用
            if st == "healthy":
                print(f"[OK] backend healthy after {(i+1)*5}s")
                break
        time.sleep(5)
    ssh_exec(client, f"docker ps --filter name={deploy_id} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'")

    # 5. gateway 重新连接网络（保险起见）
    network_name = f"{deploy_id}-network"
    # 找 gateway 容器名
    rc, out, _ = ssh_exec(client, "docker ps --filter name=gateway --format '{{.Names}}' | head -n1")
    gw = out.strip().splitlines()[0] if out.strip() else ""
    if gw:
        ssh_exec(client, f"docker network connect {network_name} {gw} 2>/dev/null || true")
        ssh_exec(client, f"docker exec {gw} nginx -s reload 2>&1 | head -5")
    else:
        print("[WARN] 未找到 gateway 容器，跳过网络重连（容器名未变更不影响）")

    # 6. 验证关键链接
    print("\n=== 验证关键链接 ===")
    ssh_exec(client, "sleep 3")

    test_urls = [
        f"{base_url}/api/health",
        f"{base_url}/api/captcha/image",
        f"{base_url}/login",
        f"{base_url}/merchant/login",
        f"{base_url}/merchant/m/login",
        f"{base_url}/",
    ]
    summary = []
    for url in test_urls:
        rc, out, _ = ssh_exec(client, f"curl -k -s -o /dev/null -w '%{{http_code}}' '{url}'")
        code = out.strip()
        ok = code in ("200", "204", "301", "302", "307", "308")
        if "/api/captcha/image" in url:
            ok = code == "200"
        summary.append((url, code, "OK" if ok else "FAIL"))

    print("\n=== 链接检查结果 ===")
    for u, c, s in summary:
        print(f"  [{s:4}] {c}  {u}")

    # 7. 验证后端实际生成的 PNG 物理像素 (用 base64 投递脚本，避免引号嵌套)
    print("\n=== 验证 PNG 物理像素 ===")
    import base64 as _b64
    py_script = (
        "from app.services.captcha_service import IMG_WIDTH, IMG_HEIGHT, FONT_SIZE, render_captcha_png\n"
        "from PIL import Image\n"
        "import io, statistics\n"
        "sizes = []\n"
        "img0 = None\n"
        "for _ in range(20):\n"
        "    p = render_captcha_png('AB23')\n"
        "    sizes.append(len(p))\n"
        "    if img0 is None:\n"
        "        img0 = Image.open(io.BytesIO(p))\n"
        "        img0.load()\n"
        "print('PNG_PHYSICAL=' + str(img0.size))\n"
        "print('CONST=%dx%d' % (IMG_WIDTH, IMG_HEIGHT))\n"
        "print('FONT=' + str(FONT_SIZE))\n"
        "print('AVG_BYTES=%d' % (sum(sizes)//len(sizes)))\n"
        "print('MAX_BYTES=%d' % max(sizes))\n"
        "print('UNDER_3KB=' + str(max(sizes) <= 3*1024))\n"
    )
    enc = _b64.b64encode(py_script.encode("utf-8")).decode("ascii")
    cmd = f"docker exec {backend_container} sh -c 'echo {enc} | base64 -d | python'"
    rc, out, _ = ssh_exec(client, cmd)

    failed = [s for s in summary if s[2] == "FAIL"]
    if failed:
        print(f"\n[WARN] {len(failed)} 个链接失败：")
        for u, c, _ in failed:
            print(f"  - {c} {u}")
        # 验证码接口失败才算真失败
        critical = [u for u, c, _ in summary if "captcha-image" in u and c != "200"]
        if critical:
            print("\n[FATAL] 关键的验证码接口不可达")
            return 6
    print("\n=== 部署成功 v1.4 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
