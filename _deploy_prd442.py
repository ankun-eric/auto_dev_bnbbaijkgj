"""
PRD-442 菜单模式 · 晴空诊室风格改造 · 增量部署脚本
=================================================

部署内容：
  - h5-web/public/menu-mode-design-system/  （新增静态资源目录）
  - 通过 SFTP 上传宿主机 + docker cp 进 h5 容器 /app/public/

不重建容器（与 PRD-441 v2 同样模式）。
完成后跑 6 个 smoke URL 验证。
"""
import os
import sys
import time
import subprocess
import urllib.request
import urllib.error

import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def main():
    print("=" * 70)
    print("PRD-442 增量部署：menu-mode-design-system + docker cp 进 h5 容器")
    print("=" * 70)

    # ---- 1) Git commit & push (with retry) ----
    subprocess.run(
        "git add h5-web/public/menu-mode-design-system "
        "miniprogram/styles/menu-mode-tokens.wxss "
        "flutter_app/lib/theme/menu_mode_theme.dart "
        "tests/test_prd442_menu_mode_design.py "
        "_deploy_prd442.py "
        ".develop_start_commit_442.txt",
        shell=True,
    )
    subprocess.run(
        'git commit -m "feat(prd-442): 菜单模式晴空诊室风格改造 v1.0（H5 design tokens + 6屏 prototype + 组件库 + 小程序 wxss + Flutter ThemeData + 16 用例 pytest)"',
        shell=True,
    )
    for i in range(3):
        r = subprocess.run(
            "git push origin master 2>&1",
            shell=True, capture_output=True, text=True,
        )
        print(r.stdout)
        if r.returncode == 0:
            print("[git push] OK")
            break
        print(f"[git push] retry {i + 1}/3 in {(i+1)*8}s")
        time.sleep((i + 1) * 8)

    # ---- 2) SSH connect ----
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=30)

    def remote_run(cmd, timeout=180):
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        rc = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out:
            print(out[:1500])
        if err:
            print("STDERR:", err[:800], file=sys.stderr)
        return rc, out, err

    sftp = ssh.open_sftp()
    local_dir = os.path.join(
        os.path.dirname(__file__),
        "h5-web", "public", "menu-mode-design-system",
    )
    remote_dir = f"{REMOTE_DIR}/h5-web/public/menu-mode-design-system"

    remote_run(f"mkdir -p {remote_dir}")

    print("\n[SFTP] 同步 menu-mode-design-system/ 到服务器宿主机...")
    for f in sorted(os.listdir(local_dir)):
        local = os.path.join(local_dir, f)
        if os.path.isfile(local):
            remote = f"{remote_dir}/{f}"
            sftp.put(local, remote)
            print(f"  ✓ {f}  ({os.path.getsize(local)} bytes)")
    sftp.close()

    # ---- 3) docker cp 进 h5 容器 ----
    print("\n[docker] 查找 h5-web 容器并 cp 文件...")
    rc, out, _ = remote_run(
        f"docker ps --filter name={DEPLOY_ID}-h5 --format '{{{{.Names}}}}'"
    )
    container = out.strip().split("\n")[0] if out.strip() else None
    if not container:
        print("ERROR: 找不到 h5 容器")
        ssh.close()
        return 1

    print(f"  容器：{container}")
    remote_run(f"docker exec {container} mkdir -p /app/public/menu-mode-design-system")
    remote_run(f"docker cp {remote_dir}/. {container}:/app/public/menu-mode-design-system/")
    remote_run(f"docker exec {container} ls -la /app/public/menu-mode-design-system/")

    ssh.close()

    # ---- 4) Smoke test ----
    print("\n" + "=" * 70)
    print("Smoke Test：6 项关键路径")
    print("=" * 70)

    paths = [
        "/menu-mode-design-system/index.html",
        "/menu-mode-design-system/prototype.html",
        "/menu-mode-design-system/components.html",
        "/menu-mode-design-system/design-tokens.css",
        "/menu-mode-design-system/design-tokens.json",
        "/menu-mode-design-system/PRD-442.md",
    ]
    pass_count = 0
    for p in paths:
        url = BASE_URL + p
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "smoke/1.0"})
            r = urllib.request.urlopen(req, timeout=15)
            body = r.read()
            print(f"  [✓] HTTP {r.status} {p}  ({len(body)} bytes)")
            pass_count += 1
        except urllib.error.HTTPError as e:
            ok = e.code in (301, 302, 307, 308)
            print(f"  [{('✓' if ok else '✗')}] HTTP {e.code} {p}")
            if ok:
                pass_count += 1
        except Exception as e:
            print(f"  [✗] {type(e).__name__} {p}: {e}")

    print("\n" + "=" * 70)
    print(f"smoke 结果：{pass_count}/{len(paths)} 通过")
    print("=" * 70)

    # 回归：确认线上 ai-home 与 PRD-441 design-system 仍然 OK
    print("\n回归检查：线上 AI 首页与 PRD-441 design-system")
    for p in ["/ai-home", "/design-system/index.html"]:
        try:
            req = urllib.request.Request(BASE_URL + p, headers={"User-Agent": "smoke/1.0"})
            r = urllib.request.urlopen(req, timeout=15)
            print(f"  [✓] HTTP {r.status} {p}")
        except urllib.error.HTTPError as e:
            ok = e.code in (200, 301, 302, 307, 308)
            mark = "✓" if ok else "✗"
            print(f"  [{mark}] HTTP {e.code} {p}")
        except Exception as e:
            print(f"  [✗] {type(e).__name__} {p}: {e}")

    return 0 if pass_count == len(paths) else 1


if __name__ == "__main__":
    sys.exit(main())
