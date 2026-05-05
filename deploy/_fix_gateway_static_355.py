"""[PRD-03 重新交付] 修复 gateway nginx 配置：补全 /miniprogram/ /apk/ /downloads/ /ipa/ /verify-miniprogram/ 静态下载 location，使产物 URL 公网可达。

修复策略：
1. 在 gateway 容器对应配置文件 /etc/nginx/conf.d/6b099ed3-...conf 的 H5 location 块**之前**插入 5 段 location：
   - /miniprogram/  → /data/static/miniprogram/
   - /apk/          → /data/static/apk/
   - /downloads/    → /data/static/downloads/
   - /ipa/          → /data/static/ipa/
   - /verify-miniprogram/ → /data/static/verify-miniprogram/
2. nginx -t 校验
3. nginx -s reload
4. 实测 5 个核心 URL 200
"""
from __future__ import annotations

import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
GW_CONF = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"


# 要插入的 5 段静态 location（顺序很关键：必须在 H5 兜底 location 之前）
STATIC_LOCATIONS = f"""
# ========= 静态产物下载（PRD-03 重新交付补全） =========
# 微信小程序 zip 包下载
location /autodev/{DEPLOY_ID}/miniprogram/ {{
    alias /data/static/miniprogram/;
    autoindex off;
    types {{ application/zip zip; }}
    add_header Content-Disposition 'attachment';
    add_header Cache-Control "public, max-age=86400" always;
}}

# 安卓 APK 下载
location /autodev/{DEPLOY_ID}/apk/ {{
    alias /data/static/apk/;
    autoindex off;
    types {{ application/vnd.android.package-archive apk; }}
    add_header Content-Disposition 'attachment';
    add_header Cache-Control "public, max-age=86400" always;
}}

# 通用 downloads 目录（核销小程序、其他兜底产物）
location /autodev/{DEPLOY_ID}/downloads/ {{
    alias /data/static/downloads/;
    autoindex off;
    add_header Content-Disposition 'attachment';
    add_header Cache-Control "public, max-age=86400" always;
}}

# iOS IPA 下载（备用，主链路是 GitHub Release）
location /autodev/{DEPLOY_ID}/ipa/ {{
    alias /data/static/ipa/;
    autoindex off;
    types {{ application/octet-stream ipa; }}
    add_header Content-Disposition 'attachment';
    add_header Cache-Control "public, max-age=86400" always;
}}

# 核销小程序 zip 备份路径
location /autodev/{DEPLOY_ID}/verify-miniprogram/ {{
    alias /data/static/verify-miniprogram/;
    autoindex off;
    types {{ application/zip zip; }}
    add_header Content-Disposition 'attachment';
    add_header Cache-Control "public, max-age=86400" always;
}}
# ========= /静态产物下载（PRD-03 重新交付补全） =========

"""


def run(ssh, cmd, timeout=180):
    print(f"\n[REMOTE] $ {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[:4000])
    if err.strip():
        print("STDERR:", err[:2000])
    return code, out, err


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, 22, USER, PASSWORD, timeout=30)

    print("=== 1. 备份原配置 ===")
    run(ssh, f"cp -f {GW_CONF} {GW_CONF}.bak.before_prd03_redelivery_$(date +%Y%m%d_%H%M%S)")

    print("=== 2. 读取当前配置内容 ===")
    sftp = ssh.open_sftp()
    with sftp.open(GW_CONF, "r") as f:
        original = f.read().decode("utf-8")
    print(f"原配置 {len(original)} 字节")

    # 防重复插入（幂等）
    if "静态产物下载（PRD-03 重新交付补全）" in original:
        print(">>> 已包含 PRD-03 静态 location，跳过插入，直接进入 reload 验证 <<<")
        new_content = original
    else:
        # 找到 H5 兜底 location 之前的位置插入
        # 标记： "# H5 用户端"
        marker = "# H5 用户端"
        idx = original.find(marker)
        if idx == -1:
            print("FAIL: 找不到 '# H5 用户端' 标记，无法定位插入点")
            ssh.close()
            return 2
        new_content = original[:idx] + STATIC_LOCATIONS + original[idx:]
        print(f"将在偏移 {idx} 处插入 {len(STATIC_LOCATIONS)} 字节静态 location")

        with sftp.open(GW_CONF, "w") as f:
            f.write(new_content)
        print(f"新配置 {len(new_content)} 字节，已写回 {GW_CONF}")

    sftp.close()

    print("=== 3. nginx -t 校验 ===")
    code, out, _ = run(ssh, "docker exec gateway nginx -t 2>&1")
    if code != 0:
        print("FAIL: nginx -t 失败，回滚配置")
        run(
            ssh,
            f"cp -f $(ls -t {GW_CONF}.bak.before_prd03_redelivery_* | head -1) {GW_CONF}",
        )
        ssh.close()
        return 3

    print("=== 4. nginx -s reload ===")
    code, _, _ = run(ssh, "docker exec gateway nginx -s reload 2>&1")
    if code != 0:
        print("FAIL: nginx reload 失败")
        ssh.close()
        return 4

    print("=== 5. 实测下载 URL 全部 200 ===")
    base = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
    targets = [
        ("/miniprogram/miniprogram_20260505_180514_8267.zip", "PRD-03 小程序包"),
        ("/apk/bini_health_android_reschedule_btn_20260505_134055_a3bf.apk", "PRD-03 安卓 APK"),
        ("/downloads/verify_miniprogram_20260505_190014_1348.zip", "PRD-05 核销小程序包"),
    ]
    fail = []
    for path, label in targets:
        code, out, _ = run(
            ssh,
            f"curl -sI -o /dev/null -w 'code=%{{http_code}} size=%{{size_download}} ctype=%{{content_type}}' '{base}{path}' && echo",
        )
        # 只看是否 200
        if "code=200" not in out:
            fail.append((path, label, out.strip()))

    ssh.close()
    if fail:
        print("\nFAIL: 部分链接仍未 200：")
        for p, l, msg in fail:
            print(f" - [{l}] {p}: {msg}")
        return 5

    print("\nOK: 所有 PRD-03 / PRD-05 静态产物 URL 200")
    return 0


if __name__ == "__main__":
    sys.exit(main())
