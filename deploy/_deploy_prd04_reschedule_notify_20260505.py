# -*- coding: utf-8 -*-
"""[PRD-04 改期通知三通道 v1.0] 部署脚本。

变更文件清单：
  1) backend/app/services/reschedule_notification.py
        - 新增 _send_wechat_work_alert 企业微信告警函数
        - notify_order_rescheduled 在 all_failed 时调用告警
        - to_dict 输出 wechat_work_alert
  2) backend/app/api/merchant.py
        - merchant_get_order_detail 增加 last_reschedule_notify_status / last_reschedule_notify
  3) backend/tests/test_prd04_reschedule_notify_v1.py（新增）
  4) h5-web/src/app/merchant/m/orders/[id]/page.tsx
        - 商家手机端订单详情页展示通知状态卡片

部署步骤：
  - SFTP 上传 4 个文件
  - docker compose build backend h5-web
  - docker compose up -d backend h5-web
  - 容器内 pytest backend/tests/test_prd04_reschedule_notify_v1.py + test_reschedule_notification_v1.py
  - 8 URL HTTPS 健康检查
"""
from __future__ import annotations

import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FILES = [
    ("backend/app/services/reschedule_notification.py",
     f"{REMOTE_ROOT}/backend/app/services/reschedule_notification.py"),
    ("backend/app/api/merchant.py",
     f"{REMOTE_ROOT}/backend/app/api/merchant.py"),
    ("backend/tests/test_prd04_reschedule_notify_v1.py",
     f"{REMOTE_ROOT}/backend/tests/test_prd04_reschedule_notify_v1.py"),
    ("h5-web/src/app/merchant/m/orders/[id]/page.tsx",
     f"{REMOTE_ROOT}/h5-web/src/app/merchant/m/orders/[id]/page.tsx"),
]


def log(*a):
    print(*a, flush=True)


def upload_files(ssh: paramiko.SSHClient):
    sftp = ssh.open_sftp()
    try:
        for local_rel, remote_abs in FILES:
            local_abs = os.path.join(LOCAL_ROOT, local_rel.replace("/", os.sep))
            if not os.path.exists(local_abs):
                log(f"[SKIP] 本地文件不存在: {local_abs}")
                continue
            log(f"[SFTP] {local_rel}  ->  {remote_abs}")
            # 确保目标目录存在
            remote_dir = os.path.dirname(remote_abs)
            try:
                sftp.stat(remote_dir)
            except IOError:
                # 递归创建
                _, ok, _ = ssh_exec(ssh, f"mkdir -p {remote_dir}")
            sftp.put(local_abs, remote_abs)
    finally:
        sftp.close()


def ssh_exec(ssh: paramiko.SSHClient, cmd: str, timeout: int = 600):
    log(f"[SSH] $ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        log(out)
    if err:
        log("[stderr]", err)
    return code, out, err


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    log(f"[SSH] 连接 {HOST}:{PORT} as {USER} ...")
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    try:
        upload_files(ssh)

        log("\n========== 重建后端 + h5-web ==========")
        ssh_exec(ssh, f"cd {REMOTE_ROOT} && docker compose build backend h5-web", timeout=900)
        ssh_exec(ssh, f"cd {REMOTE_ROOT} && docker compose up -d backend h5-web", timeout=300)
        # 给后端一点启动时间
        time.sleep(8)

        log("\n========== 容器内安装测试依赖（幂等） ==========")
        backend_container = f"{DEPLOY_ID}-backend"
        ssh_exec(
            ssh,
            f"docker exec {backend_container} pip install -q --no-cache-dir "
            f"pytest pytest-asyncio aiosqlite httpx",
            timeout=300,
        )

        log("\n========== 容器内 pytest（PRD-04 + 历史 reschedule_notification 套件） ==========")
        code, out, _ = ssh_exec(
            ssh,
            f"docker exec {backend_container} python -m pytest "
            f"tests/test_prd04_reschedule_notify_v1.py "
            f"tests/test_reschedule_notification_v1.py "
            f"-v --noconftest -p no:cacheprovider",
            timeout=600,
        )
        if code != 0:
            log(f"[ERROR] pytest 退出码 {code}")
            sys.exit(2)

        log("\n========== 8 个核心 URL HTTPS 健康检查 ==========")
        base = f"https://{HOST}/autodev/{DEPLOY_ID}"
        urls = [
            f"{base}/",                       # H5 用户端
            f"{base}/admin/",                 # Admin 登录
            f"{base}/merchant/calendar/",     # 商家 PC 日历
            f"{base}/merchant/m/",            # 商家手机端首页
            f"{base}/api/health",             # 后端健康
            f"{base}/api/docs",               # Swagger
            f"{base}/api/admin/payment-channels",  # 401 = 接口存活
            f"{base}/api/merchant/orders/1/detail?store_id=1",  # 401 = 接口存活
        ]
        for u in urls:
            ssh_exec(
                ssh,
                f'curl -s -o /dev/null -w "%{{http_code}}  {u}\\n" "{u}"',
                timeout=30,
            )

        log("\n[DONE] PRD-04 部署完成")

    finally:
        ssh.close()


if __name__ == "__main__":
    main()
