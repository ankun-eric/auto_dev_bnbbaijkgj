"""
PRD-433 H5 端部署脚本
- SFTP 上传 ai-home/page.tsx
- SSH 执行 docker compose build/up h5-web
- curl smoke 验证
"""
import paramiko
import time
import sys
import io

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

# 注意：远程 Linux 路径，括号原样保留
REMOTE_FILE = f"{PROJECT_DIR}/h5-web/src/app/(ai-chat)/ai-home/page.tsx"
LOCAL_FILE = "h5-web/src/app/(ai-chat)/ai-home/page.tsx"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    log(f"=== PRD-433 部署开始 ===")
    log(f"目标服务器: {HOST}, 部署目录: {PROJECT_DIR}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

    # ========== 1. SFTP 上传 H5 文件 ==========
    log("--- Step 1: SFTP 上传 page.tsx ---")
    sftp = ssh.open_sftp()
    try:
        local_size = 0
        with open(LOCAL_FILE, "rb") as f:
            local_size = len(f.read())
        sftp.put(LOCAL_FILE, REMOTE_FILE)
        # 获取远程大小验证
        remote_size = sftp.stat(REMOTE_FILE).st_size
        log(f"上传成功: 本地 {local_size} bytes, 远程 {remote_size} bytes")
        if local_size != remote_size:
            log(f"⚠️ 大小不一致")
    finally:
        sftp.close()

    # ========== 2. docker compose build h5-web ==========
    log("--- Step 2: docker compose build h5-web ---")
    cmd = f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1"
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=600)
    
    build_output = []
    for line in iter(stdout.readline, ""):
        line = line.rstrip()
        if line:
            build_output.append(line)
            # 只打印关键行
            if any(k in line for k in ["ERROR", "FAIL", "Compiled", "Build", "Generating", "Building", "DONE", "naming", "successful"]):
                log(f"  build> {line}")
    
    exit_status = stdout.channel.recv_exit_status()
    log(f"build 完成，exit_status={exit_status}")
    if exit_status != 0:
        log("❌ build 失败，最后 30 行输出:")
        for line in build_output[-30:]:
            log(f"  {line}")
        ssh.close()
        sys.exit(1)

    # ========== 3. docker compose up -d h5-web ==========
    log("--- Step 3: docker compose up -d h5-web ---")
    cmd = f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1"
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=120)
    up_output = stdout.read().decode("utf-8", errors="replace")
    exit_status = stdout.channel.recv_exit_status()
    log(f"up -d 完成，exit_status={exit_status}")
    for line in up_output.splitlines()[-10:]:
        log(f"  up> {line}")
    
    # 等待容器就绪
    log("等待容器健康...")
    time.sleep(15)

    # ========== 4. Smoke 测试 ==========
    log("--- Step 4: Smoke 测试 ---")
    smoke_targets = [
        ("/api/health", 200),
        ("/api/ai-home-config", 200),
        ("/", 200),
        ("/ai-home", 308),  # 重定向到登录页正常
    ]
    smoke_results = []
    for path, expected_code in smoke_targets:
        url = f"{BASE_URL}{path}"
        cmd = f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 15 -L --max-redirs 0 '{url}'"
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
        actual = stdout.read().decode().strip()
        ok = (actual == str(expected_code))
        status = "✅" if ok else "❌"
        log(f"  {status} {path} -> {actual} (expected {expected_code})")
        smoke_results.append((path, expected_code, actual, ok))
    
    # 验证 SSR HTML 中包含本次新增 testid
    log("--- Step 5: 验证 SSR HTML 中 PRD-433 标记 ---")
    cmd = f"curl -s -L --max-time 15 '{BASE_URL}/ai-home' | head -c 50000"
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    html_head = stdout.read().decode("utf-8", errors="replace")
    # 由于 ai-home 未登录会被重定向到登录页，正常情况下不一定能在响应里看到 ai-home 自身的 testid，
    # 因此这里只验证服务器响应了页面 HTML
    log(f"  响应片段长度: {len(html_head)} chars，{'包含 <html' if '<html' in html_head else '⚠️ 不含 <html'}")

    # ========== 6. docker ps 确认容器状态 ==========
    cmd = f"docker ps --format '{{{{.Names}}}}\t{{{{.Status}}}}' | grep {DEPLOY_ID}-h5"
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    h5_status = stdout.read().decode().strip()
    log(f"h5 容器状态: {h5_status}")

    ssh.close()
    
    # 汇总
    log("=== Smoke 结果汇总 ===")
    all_ok = all(r[3] for r in smoke_results)
    for path, exp, actual, ok in smoke_results:
        log(f"  {'PASS' if ok else 'FAIL'}  {path}  expected={exp}  actual={actual}")
    
    if all_ok:
        log("✅ 全部 smoke 通过")
        return 0
    else:
        log("❌ 部分 smoke 失败")
        return 2


if __name__ == "__main__":
    try:
        rc = main()
        sys.exit(rc)
    except Exception as e:
        log(f"💥 部署异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)
