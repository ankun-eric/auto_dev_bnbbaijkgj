# -*- coding: utf-8 -*-
"""[PRD｜登录页布局优化 v1.0] 部署脚本（cursor_prompt_363）.

本次变更涉及 3 端代码：
  - h5-web/src/app/login/page.tsx          —— 顶部绿色渐变 + LOGO 圆形托盘 + 表单上浮卡片 + 协议二次确认
  - miniprogram/pages/login/index.wxml     —— 同结构（rpx）
  - miniprogram/pages/login/index.wxss     —— 渐变 + 圆形托盘 + 表单卡片 + 验证码不换行
  - miniprogram/pages/login/index.js       —— loginByPhone 增加协议二次确认弹窗
  - flutter_app/lib/screens/login_screen.dart —— 顶部 LinearGradient + ClipOval LOGO + Transform.translate(-28) 上浮表单 + showDialog 协议确认

部署步骤（SFTP + git + docker，按服务器实际架构执行）：
  1) 直接 SFTP 上传 5 个文件（避免依赖 git push 网络重试）
  2) docker compose build h5-web --no-cache
  3) docker compose up -d h5-web
  4) gateway nginx -s reload
  5) HTTPS 健康检查（h5/api/admin/login 页面）

服务器：
  HOST: newbb.test.bangbangvip.com
  USER: ubuntu / Newbang888
  DEPLOY_ID: 6b099ed3-7175-4a78-91f4-44570c84ed27
"""
from __future__ import annotations

import os
import sys
import time
import urllib.request

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FILES = [
    ("h5-web/src/app/login/page.tsx",
     f"{REMOTE_ROOT}/h5-web/src/app/login/page.tsx"),
    ("miniprogram/pages/login/index.wxml",
     f"{REMOTE_ROOT}/miniprogram/pages/login/index.wxml"),
    ("miniprogram/pages/login/index.wxss",
     f"{REMOTE_ROOT}/miniprogram/pages/login/index.wxss"),
    ("miniprogram/pages/login/index.js",
     f"{REMOTE_ROOT}/miniprogram/pages/login/index.js"),
    ("flutter_app/lib/screens/login_screen.dart",
     f"{REMOTE_ROOT}/flutter_app/lib/screens/login_screen.dart"),
]


def log(*a):
    print(*a, flush=True)


def ssh_exec(ssh: paramiko.SSHClient, cmd: str, timeout: int = 900):
    log(f"[SSH] $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        log(out.rstrip())
    if err.strip():
        log("[STDERR]", err.rstrip())
    return code, out, err


def upload_files(ssh: paramiko.SSHClient):
    sftp = ssh.open_sftp()
    try:
        for local_rel, remote_abs in FILES:
            local_abs = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
            if not os.path.exists(local_abs):
                log(f"[SKIP] 本地文件不存在: {local_abs}")
                continue
            log(f"[SFTP] {local_rel}  ->  {remote_abs}")
            remote_dir = os.path.dirname(remote_abs)
            try:
                sftp.stat(remote_dir)
            except IOError:
                ssh_exec(ssh, f"mkdir -p {remote_dir}")
            sftp.put(local_abs, remote_abs)
    finally:
        sftp.close()


def http_check(url: str, expect=(200, 401, 403)):
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            sc = resp.getcode()
    except urllib.error.HTTPError as e:
        sc = e.code
    except Exception as e:
        log(f"[HTTP] {url}  EXC: {e}")
        return False
    ok = sc in expect
    log(f"[HTTP] {url}  -> {sc}  {'OK' if ok else 'FAIL'}")
    return ok


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    log(f"[SSH] connect {USER}@{HOST}:{PORT}")
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30, banner_timeout=30)

    try:
        upload_files(ssh)

        # 验证服务器侧文件就位
        ssh_exec(ssh, f"head -n 3 {REMOTE_ROOT}/h5-web/src/app/login/page.tsx")
        ssh_exec(ssh, f"grep -c 'top-brand' {REMOTE_ROOT}/h5-web/src/app/login/page.tsx")
        ssh_exec(ssh, f"grep -c 'logo-circle' {REMOTE_ROOT}/miniprogram/pages/login/index.wxss")
        ssh_exec(ssh, f"grep -c 'Transform.translate' {REMOTE_ROOT}/flutter_app/lib/screens/login_screen.dart")

        # 重新构建 h5-web（小程序无需 docker 构建；Flutter 走 GitHub Actions 远程构建）
        log("[STEP] docker compose build h5-web --no-cache")
        ssh_exec(ssh, f"cd {REMOTE_ROOT} && docker compose build h5-web --no-cache 2>&1 | tail -n 60", timeout=1800)
        log("[STEP] docker compose up -d h5-web")
        ssh_exec(ssh, f"cd {REMOTE_ROOT} && docker compose up -d h5-web", timeout=120)

        # 等待容器启动
        time.sleep(8)

        # 容器状态
        ssh_exec(ssh, f"cd {REMOTE_ROOT} && docker compose ps")

        # gateway nginx reload（确保静态路由生效）
        ssh_exec(ssh, "docker exec gateway nginx -t && docker exec gateway nginx -s reload")

        # HTTP 健康检查
        base = f"https://{HOST}/autodev/{DEPLOY_ID}"
        urls = [
            (f"{base}/", (200,)),
            (f"{base}/login/", (200,)),
            (f"{base}/api/openapi.json", (200,)),
            (f"{base}/admin/", (200,)),
        ]
        all_ok = True
        for u, expect in urls:
            ok = http_check(u, expect=expect)
            all_ok = all_ok and ok

        if all_ok:
            log("\n=========================== ✅ 部署成功 ===========================")
        else:
            log("\n=========================== ❌ 部分 URL 异常 ===========================")
            sys.exit(1)
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
