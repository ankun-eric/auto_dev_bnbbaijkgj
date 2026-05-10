"""
PRD-441 增量部署：仅同步 design-system 静态文件（不需重建 h5-web 容器，
因为 Next.js standalone 模式打包时 public/ 已经被 COPY 到镜像里，但通过 docker
volume 或宿主机挂载也可以即时生效。这里直接 docker cp 进容器最稳）。
"""
import os
import sys
import time
import subprocess
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def main():
    print("=" * 70)
    print("PRD-441 增量部署：sync design-system + docker cp 进 h5-web 容器")
    print("=" * 70)

    # git push（带重试）
    subprocess.run("git add h5-web/public/design-system _deploy_prd441_v2.py", shell=True)
    subprocess.run('git commit -m "feat(prd-441): add PRD-441.md english copy + incremental deploy" 2>&1', shell=True)
    for i in range(3):
        r = subprocess.run("git push origin master 2>&1", shell=True, capture_output=True, text=True)
        print(r.stdout, r.stderr)
        if r.returncode == 0:
            break
        time.sleep(8)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PWD, timeout=30)

    sftp = ssh.open_sftp()
    local_dir = os.path.join(os.path.dirname(__file__), "h5-web", "public", "design-system")
    remote_dir = f"{REMOTE_DIR}/h5-web/public/design-system"

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

    remote_run(f"mkdir -p {remote_dir}")

    print("\n[SFTP] 同步 design-system/ 到服务器宿主机...")
    for f in os.listdir(local_dir):
        local = os.path.join(local_dir, f)
        remote = f"{remote_dir}/{f}"
        sftp.put(local, remote)
        print(f"  ✓ {f}")
    sftp.close()

    # 找 h5-web 容器并 docker cp 进去
    print("\n[docker] 查找 h5-web 容器并 cp 文件...")
    rc, out, _ = remote_run(f"docker ps --filter name={DEPLOY_ID}-h5 --format '{{{{.Names}}}}'")
    container = out.strip().split("\n")[0] if out.strip() else None
    if not container:
        print("ERROR: 找不到 h5 容器")
        ssh.close()
        return 1

    print(f"  容器：{container}")
    # docker cp design-system 整个目录到容器内 public/
    remote_run(f"docker exec {container} mkdir -p /app/public/design-system")
    remote_run(f"docker cp {remote_dir}/. {container}:/app/public/design-system/")
    remote_run(f"docker exec {container} ls -la /app/public/design-system/")

    ssh.close()

    # smoke test (Python urllib)
    print("\n" + "=" * 70)
    print("Smoke Test：6 项")
    print("=" * 70)
    import urllib.request
    import urllib.parse

    paths = [
        "/design-system/",
        "/design-system/index.html",
        "/design-system/prototype.html",
        "/design-system/design-tokens.css",
        "/design-system/design-tokens.json",
        "/design-system/PRD-441.md",
    ]
    pass_count = 0
    for p in paths:
        url = BASE_URL + p
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "smoke/1.0"})
            r = urllib.request.urlopen(req, timeout=15)
            print(f"  [✓] HTTP {r.status} {p}  ({len(r.read())} bytes)")
            pass_count += 1
        except urllib.error.HTTPError as e:
            print(f"  [{('✓' if e.code in (301,302,307,308) else '✗')}] HTTP {e.code} {p}")
            if e.code in (301,302,307,308):
                pass_count += 1
        except Exception as e:
            print(f"  [✗] {type(e).__name__} {p}: {e}")

    print("\n" + "=" * 70)
    print(f"smoke 结果：{pass_count}/{len(paths)} 通过")
    print("=" * 70)
    return 0 if pass_count == len(paths) else 1


if __name__ == "__main__":
    sys.exit(main())
