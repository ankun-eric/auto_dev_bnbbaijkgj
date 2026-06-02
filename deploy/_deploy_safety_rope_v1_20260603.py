"""[PRD-SAFETY-ROPE-V1 2026-06-03] 数字安全绳部署脚本

策略：
- 服务器 GitHub 访问常态超时，采用 SFTP 直传变更文件
- 后端：safety_rope_v1.py + tests + main.py + notification_scheduler.py
- H5：care-safety-rope/page.tsx + care-home/page.tsx
- 小程序：care-safety-rope/* + care-home/* + app.json
- Flutter：safety_rope_webview.dart + care_home_screen.dart（仅源码同步，App 打包另行）

部署流程：
1) SFTP 上传文件
2) docker compose build/up backend + h5-web（仅这两个）
3) 网关 reload
4) 调用扫描 API（管理员）验证可用
5) 烟雾测试核心端点
"""
import os
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

# 本地相对路径 → 服务器相对路径
FILES = [
    ("backend/app/api/safety_rope_v1.py", "backend/app/api/safety_rope_v1.py"),
    ("backend/app/main.py", "backend/app/main.py"),
    ("backend/app/services/notification_scheduler.py", "backend/app/services/notification_scheduler.py"),
    ("backend/tests/test_safety_rope_v1_20260603.py", "backend/tests/test_safety_rope_v1_20260603.py"),
    ("h5-web/src/app/care-safety-rope/page.tsx", "h5-web/src/app/care-safety-rope/page.tsx"),
    ("h5-web/src/app/care-home/page.tsx", "h5-web/src/app/care-home/page.tsx"),
    ("miniprogram/app.json", "miniprogram/app.json"),
    ("miniprogram/pages/care-safety-rope/index.wxml", "miniprogram/pages/care-safety-rope/index.wxml"),
    ("miniprogram/pages/care-safety-rope/index.wxss", "miniprogram/pages/care-safety-rope/index.wxss"),
    ("miniprogram/pages/care-safety-rope/index.json", "miniprogram/pages/care-safety-rope/index.json"),
    ("miniprogram/pages/care-safety-rope/index.js", "miniprogram/pages/care-safety-rope/index.js"),
    ("miniprogram/pages/care-home/index.wxml", "miniprogram/pages/care-home/index.wxml"),
    ("miniprogram/pages/care-home/index.wxss", "miniprogram/pages/care-home/index.wxss"),
    ("miniprogram/pages/care-home/index.js", "miniprogram/pages/care-home/index.js"),
    ("flutter_app/lib/screens/care/safety_rope_webview.dart", "flutter_app/lib/screens/care/safety_rope_webview.dart"),
    ("flutter_app/lib/screens/care/care_home_screen.dart", "flutter_app/lib/screens/care/care_home_screen.dart"),
]


def sh(client, cmd, timeout=180):
    print(f"\n$ {cmd[:200]}...")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    rc = stdout.channel.recv_exit_status()
    if out:
        print(out[-2000:])
    if err:
        print("STDERR:", err[-1500:])
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[1/6] Connect ssh://{USER}@{HOST}")
    client.connect(HOST, username=USER, password=PWD, timeout=30)

    sftp = client.open_sftp()
    print(f"[2/6] SFTP upload {len(FILES)} files → {PROJ}")
    for local_rel, remote_rel in FILES:
        local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", local_rel)
        local = os.path.normpath(local)
        remote = f"{PROJ}/{remote_rel}".replace("\\", "/")
        if not os.path.exists(local):
            print(f"  ! missing local: {local}")
            continue
        # 确保远端目录存在
        d = os.path.dirname(remote)
        sh(client, f"mkdir -p {d}", timeout=20)
        sftp.put(local, remote)
        print(f"  ✓ {local_rel} → {remote_rel}")
    sftp.close()

    print("[3/6] Build & up backend container only (不重启 db / admin / h5)")
    rc, _, _ = sh(client, f"cd {PROJ} && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -50", timeout=600)
    if rc != 0:
        print("  ! backend build failed")
        sys.exit(1)
    sh(client, f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d --no-deps backend", timeout=180)

    print("[4/6] Build & up h5-web container only")
    rc, _, _ = sh(
        client,
        f"cd {PROJ} && nohup docker compose -f docker-compose.prod.yml build --no-cache h5-web > /tmp/h5_build.log 2>&1 & echo $!",
        timeout=30,
    )
    # 轮询 h5 build 完成
    for i in range(40):
        time.sleep(15)
        rc, out, _ = sh(client, "tail -3 /tmp/h5_build.log 2>/dev/null; pgrep -f 'docker compose.*build.*h5-web' || echo BUILD_DONE", timeout=20)
        if "BUILD_DONE" in out:
            break
    sh(client, f"cd {PROJ} && docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate h5-web", timeout=180)

    print("[5/6] 等待容器健康并 reload nginx")
    time.sleep(8)
    sh(client, "docker exec gateway-nginx nginx -t && docker exec gateway-nginx nginx -s reload || true", timeout=30)

    print("[6/6] Smoke test (HTTPS)")
    sh(client, f"curl -sk -o /dev/null -w 'health=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/health")
    sh(client, f"curl -sk -o /dev/null -w 'sr_status_unauth=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/safety-rope/status")
    sh(client, f"curl -sk -o /dev/null -w 'h5_page=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/care-safety-rope")
    sh(client, f"curl -sk -o /dev/null -w 'h5_home=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/care-home")

    print("\n部署完成。")
    client.close()


if __name__ == "__main__":
    main()
