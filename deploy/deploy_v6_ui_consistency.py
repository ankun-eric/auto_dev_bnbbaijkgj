"""PRD v6 UI 视觉一致性优化 — 全量部署到测试服务器。

涉及变更:
- backend: home_config.py、init_data.py、health_plan_v2.py、schemas/home_config.py
- h5-web: 大量 NavBar 改造、字号体系、健康计划三子页、统计图、首页搜索栏等
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


def collect_files(local_root):
    """收集本期需要部署的所有文件 (基于 git status 修改/新增文件，仅 backend/h5)。"""
    files = []
    for root, dirs, fnames in os.walk(local_root):
        rel_root = os.path.relpath(root, local_root).replace(os.sep, "/")
        skip = (rel_root == "." or rel_root.startswith("backend/") or rel_root.startswith("h5-web/"))
        if not skip:
            continue
        if "node_modules" in rel_root or ".next" in rel_root or "__pycache__" in rel_root:
            continue
        for fn in fnames:
            files.append(os.path.join(rel_root, fn).replace("\\", "/"))
    return files


CHANGED_FILES = [
    # backend
    "backend/app/api/health_plan_v2.py",
    "backend/app/api/home_config.py",
    "backend/app/init_data.py",
    "backend/app/schemas/home_config.py",
    # h5-web 全量
]


def make_tarball_from_git(local_root):
    """打包所有 git 修改和新增的 backend/h5 文件。"""
    import subprocess
    # status -z 输出
    r = subprocess.run(
        ["git", "-C", local_root, "status", "--porcelain"],
        capture_output=True, text=True, encoding="utf-8"
    )
    files = []
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        # 格式: "XY path"
        path = line[3:].strip()
        if path.startswith("backend/") or path.startswith("h5-web/"):
            if "tsconfig.tsbuildinfo" in path or ".next/" in path:
                continue
            files.append(path)

    # 加入未跟踪 (已含在 status)
    print(f"  collected {len(files)} files")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in files:
            full = os.path.join(local_root, rel.replace("/", os.sep))
            if os.path.exists(full):
                tar.add(full, arcname=rel)
            else:
                print(f"  [warn] missing: {rel}")
    buf.seek(0)
    return buf.getvalue(), files


def main():
    local_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    c = connect()
    print(f"Connected to {HOST}")

    print("\n=== Step 1: 打包并上传源代码 ===")
    tar_bytes, file_list = make_tarball_from_git(local_root)
    print(f"  package size: {len(tar_bytes)} bytes, {len(file_list)} files")
    remote_tar = f"/tmp/{DEPLOY_ID}-v6-ui.tar.gz"
    sftp = c.open_sftp()
    with sftp.open(remote_tar, "wb") as f:
        f.write(tar_bytes)
    sftp.close()
    run(c, f"cd {PROJECT_DIR} && tar -xzf {remote_tar} && rm -f {remote_tar}", check=True)

    # 校验关键改动
    run(c, f"grep -c 'GreenNavBar' {PROJECT_DIR}/h5-web/src/components/GreenNavBar.tsx")
    run(c, f"grep -c 'plan_rankings' {PROJECT_DIR}/backend/app/api/health_plan_v2.py")
    run(c, f"grep -c '想找什么服务/商品' {PROJECT_DIR}/backend/app/api/home_config.py")

    print("\n=== Step 2: docker compose build h5-web (Next.js 需重建) ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build h5-web 2>&1 | tail -40",
        timeout=1500, check=True)

    print("\n=== Step 3: 重启服务 (backend + h5-web) ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate backend h5-web 2>&1 | tail -30",
        timeout=240, check=True)

    print("\n=== Step 4: 等待容器就绪 ===")
    time.sleep(20)
    for i in range(15):
        out, _, _ = run(c, f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'", quiet=True)
        ok = out.count("Up ") >= 4 and "Restarting" not in out
        print(f"  [check {i+1}] containers Up={out.count('Up ')}")
        if ok:
            break
        time.sleep(8)

    print("\n=== Step 5: 容器状态 ===")
    run(c, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'")

    print("\n=== Step 6: 链接可达性快检 ===")
    base = f"https://{DOMAIN}/autodev/{DEPLOY_ID}"
    paths = [
        "/",
        "/profile",
        "/health-plan",
        "/health-plan/medications",
        "/health-plan/checkin",
        "/health-plan/custom",
        "/health-plan/statistics",
        "/unified-orders",
        "/my-coupons",
        "/settings",
        "/api/home-config",
        "/api/health-plan/statistics",
    ]
    for path in paths:
        run(c, f"curl -s -o /dev/null -w '%{{http_code}}  {path}\\n' '{base}{path}'")

    c.close()
    print("\n=== DEPLOY DONE ===")


if __name__ == "__main__":
    main()
