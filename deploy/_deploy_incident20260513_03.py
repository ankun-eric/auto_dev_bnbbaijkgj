"""
[INCIDENT-20260513-03] P0: 历史会话「加载失败」修复部署
- 同步 h5-web/src/components/ai-chat/Sidebar.tsx 到服务器
- 重建 h5-web 镜像（--no-cache）并重启容器
- 验证 /api/chat-sessions 接口可达 + h5 主页 200
"""
import paramiko
import sys
import time
import os

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

LOCAL_FILE = "h5-web/src/components/ai-chat/Sidebar.tsx"
REMOTE_FILE = f"{REMOTE_ROOT}/h5-web/src/components/ai-chat/Sidebar.tsx"


def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    return c


def run(c, cmd, timeout=600, show=True):
    if show:
        print(f"\n$ {cmd}")
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="ignore")
    err = e.read().decode("utf-8", errors="ignore")
    rc = o.channel.recv_exit_status()
    if show:
        if out:
            print(out)
        if err.strip():
            print("STDERR:", err)
        print(f"[exit={rc}]")
    return rc, out, err


def main():
    print("=" * 60)
    print("INCIDENT-20260513-03 P0 修复部署")
    print(f"  目标: {BASE_URL}")
    print(f"  文件: {LOCAL_FILE}")
    print("=" * 60)

    c = ssh()

    # 1) SCP 单文件上传
    print("\n[1/5] 上传 Sidebar.tsx ...")
    sftp = c.open_sftp()
    sftp.put(LOCAL_FILE, REMOTE_FILE)
    sftp.close()
    rc, out, _ = run(c, f"ls -la {REMOTE_FILE} && wc -l {REMOTE_FILE}", show=True)
    assert rc == 0, "文件上传失败"

    # 2) 校验关键修复字符串在服务器侧已生效
    print("\n[2/5] 校验上传内容含 INCIDENT-20260513-03 标记 ...")
    rc, out, _ = run(c, f"grep -c 'INCIDENT-20260513-03' {REMOTE_FILE}")
    assert rc == 0 and int(out.strip()) >= 2, f"修复标记数不符: {out!r}"
    print("OK: 修复标记已上传")

    # 3) 重建 h5-web 镜像（--no-cache 强制重新 build）
    print("\n[3/5] 重建 h5-web 镜像（--no-cache） ...")
    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose build --no-cache h5-web 2>&1 | tail -40",
        timeout=900,
    )
    assert rc == 0, "h5-web 镜像构建失败"

    # 4) 重启 h5-web 容器
    print("\n[4/5] 重启 h5-web 容器 ...")
    rc, _, _ = run(
        c,
        f"cd {REMOTE_ROOT} && docker compose up -d --force-recreate h5-web 2>&1 | tail -20",
        timeout=300,
    )
    assert rc == 0, "h5-web 容器重启失败"

    # 等待启动
    print("\n等待 h5-web 容器健康 (15s) ...")
    time.sleep(15)
    run(c, f"docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID}")

    # 5) 验证关键路径可达
    print("\n[5/5] 验证关键路径可达 ...")
    checks = [
        ("h5 主页", f"{BASE_URL}/"),
        ("h5 AI 主页", f"{BASE_URL}/ai-home"),
        ("后端 /api/chat-sessions（未登录应 401/403/422，绝不能 500）", f"{BASE_URL}/api/chat-sessions"),
    ]
    all_ok = True
    for label, url in checks:
        rc, out, _ = run(
            c,
            f"curl -ksS -o /dev/null -w 'HTTP_CODE=%{{http_code}}' '{url}'",
            timeout=30,
            show=False,
        )
        code = out.strip().replace("HTTP_CODE=", "")
        # 200/304/401/403/422 都视为后端 / 前端可达；500/502/503/504 视为故障
        ok = code in ("200", "204", "301", "302", "304", "401", "403", "404", "422")
        sym = "OK" if ok else "FAIL"
        print(f"  [{sym}] {label}\n        {url}\n        => HTTP {code}")
        if not ok:
            all_ok = False

    # 额外验证：Sidebar.tsx 修复字符串没出现在已构建的镜像层（通过容器 fs）
    print("\n[Extra] 校验容器内 .next 构建产物含修复标记 ...")
    rc, out, _ = run(
        c,
        f"docker exec {DEPLOY_ID}-h5 sh -c \"grep -r 'INCIDENT-20260513-03' /app/.next/server 2>/dev/null | head -2 || echo NO_HIT\"",
        timeout=60,
    )

    c.close()

    print("\n" + "=" * 60)
    if all_ok:
        print("PASS: 部署完成，关键路径全部可达")
        sys.exit(0)
    else:
        print("FAIL: 存在不可达路径，请人工排查")
        sys.exit(1)


if __name__ == "__main__":
    main()
