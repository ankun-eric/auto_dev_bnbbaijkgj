"""V7 联合修复包部署脚本（卡片常驻 + 识药图片 + 咨询人按钮文案）。

涉及变更：
- backend: ocr.py (集成 COS 上传 + thumbnail 写入)
- h5-web: chat[sessionId]/page.tsx（删除 banner 自动收起）、drug/symptom/checkup/tcm 页（按钮文案）、drug 列表 onError 兜底
- miniprogram: pages/chat（drug banner 显示规则简化）、pages/drug（thumbnail onError 兜底）
- flutter_app: drug_screen.dart（优先用 original_image_url）
"""
import os
import io
import sys
import time
import tarfile
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DOMAIN = "newbb.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)
    return c


def run(c, cmd, timeout=900, check=False, quiet=False):
    if not quiet:
        print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if not quiet:
        if out:
            print(out[-2500:])
        if err:
            print(f"[stderr] {err[-1500:]}")
        print(f"[exit {code}]")
    if check and code != 0:
        raise RuntimeError(f"FAIL ({code}): {cmd}")
    return out, err, code


# 本次需要部署的关键文件（手动列出，避免误传未变更文件）
CHANGED_FILES = [
    "backend/app/api/ocr.py",
    "h5-web/src/app/chat/[sessionId]/page.tsx",
    "h5-web/src/app/drug/page.tsx",
    "h5-web/src/app/symptom/page.tsx",
    "h5-web/src/app/checkup/page.tsx",
    "h5-web/src/app/tcm/page.tsx",
]


def make_tarball(local_root):
    files = list(CHANGED_FILES)
    print(f"  collected {len(files)} files")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in files:
            full = os.path.join(local_root, rel.replace("/", os.sep))
            if os.path.exists(full):
                tar.add(full, arcname=rel)
                print(f"    + {rel}")
            else:
                print(f"  [warn] missing: {rel}")
    buf.seek(0)
    return buf.getvalue(), files


def main():
    local_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    c = connect()
    print(f"Connected to {HOST}")

    print("\n=== Step 1: 打包并上传源代码 ===")
    tar_bytes, file_list = make_tarball(local_root)
    print(f"  package size: {len(tar_bytes)} bytes, {len(file_list)} files")
    remote_tar = f"/tmp/{DEPLOY_ID}-combo-v7.tar.gz"
    sftp = c.open_sftp()
    with sftp.open(remote_tar, "wb") as f:
        f.write(tar_bytes)
    sftp.close()
    run(c, f"cd {PROJECT_DIR} && tar -xzf {remote_tar} && rm -f {remote_tar}", check=True)

    # 校验关键改动
    print("\n=== Step 2: 关键改动验证 ===")
    run(c, f"grep -c 'try_cos_upload' {PROJECT_DIR}/backend/app/api/ocr.py")
    run(c, f"grep -c 'AI 开始分析' {PROJECT_DIR}/h5-web/src/app/drug/page.tsx")
    run(c, f"grep -c 'AI 开始分析' {PROJECT_DIR}/h5-web/src/app/symptom/page.tsx")
    run(c, f"grep -c 'banner stays persistent' {PROJECT_DIR}/h5-web/src/app/chat/\\[sessionId\\]/page.tsx")

    print("\n=== Step 3: docker compose build h5-web (Next.js 需重建) ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -40",
        timeout=1500, check=True)

    print("\n=== Step 4: 重启服务 (backend + h5-web) ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate backend h5-web 2>&1 | tail -30",
        timeout=240, check=True)

    print("\n=== Step 5: 等待容器就绪 ===")
    time.sleep(20)
    for i in range(15):
        out, _, _ = run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'", quiet=True)
        ok = out.count("Up ") >= 3 and "Restarting" not in out
        print(f"  [check {i+1}] containers Up={out.count('Up ')}")
        if ok:
            break
        time.sleep(8)

    print("\n=== Step 6: 容器状态 ===")
    run(c, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'")

    print("\n=== Step 7: 链接可达性快检 ===")
    base = f"https://{DOMAIN}/autodev/{DEPLOY_ID}"
    paths = [
        "/",
        "/drug",
        "/symptom",
        "/checkup",
        "/tcm",
        "/chat/1?type=drug_identify&member=%E6%9C%AC%E4%BA%BA",
        "/chat/1?type=constitution&member=%E6%9C%AC%E4%BA%BA",
        "/api/home-config",
    ]
    for path in paths:
        run(c, f"curl -s -o /dev/null -w '%{{http_code}}  {path}\\n' '{base}{path}'")

    c.close()
    print("\n=== DEPLOY DONE ===")


if __name__ == "__main__":
    main()
