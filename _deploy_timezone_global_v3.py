"""[BUG_FIX_TIMEZONE_GLOBAL_V3_20260517] v3 全系统时区根治（全端版）部署脚本

通过 SFTP 把本地 git status 中所有相关修改文件上传到远程项目目录，
然后重建 h5-web 和 admin-web 两个前端容器，等待健康，最后输出状态。
"""
from __future__ import annotations

import os
import sys
import time
import subprocess
from pathlib import Path
from typing import List, Tuple

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
NETWORK = f"{PROJECT_ID}-network"

# 候选远程目录（按任务要求优先 /home/ubuntu/{PROJECT_ID}）
REMOTE_DIR_CANDIDATES = [
    f"/home/ubuntu/{PROJECT_ID}",
    f"/home/ubuntu/autodev/{PROJECT_ID}",
    f"/root/autodev/{PROJECT_ID}",
]

LOCAL_ROOT = Path(__file__).resolve().parent

# 排除规则
EXCLUDE_PREFIXES = (
    "user_docs/",
    "apk_",
    "ipa_",
)
EXCLUDE_BASENAME_STARTSWITH = ("_",)  # 临时脚本 _xxx
EXCLUDE_SUFFIX = (".md", ".txt")


def _ssh() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    return cli


def _run(cli, cmd, timeout=180):
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def _find_remote_dir(cli) -> str:
    for d in REMOTE_DIR_CANDIDATES:
        c, _, _ = _run(cli, f"test -d {d} && echo OK || echo NO")
        if c == 0:
            c2, out, _ = _run(cli, f"ls -1 {d}/docker-compose*.yml 2>/dev/null | head -n1")
            if out.strip():
                print(f"[remote_dir] found {d} (compose: {out.strip()})")
                return d
    # 兜底：第一个候选
    print(f"[remote_dir] fallback {REMOTE_DIR_CANDIDATES[0]}")
    return REMOTE_DIR_CANDIDATES[0]


def _mkdir_p(sftp, remote_dir: str):
    remote_dir = remote_dir.replace("\\", "/")
    try:
        sftp.stat(remote_dir)
        return
    except IOError:
        pass
    parts = remote_dir.strip("/").split("/")
    cur = ""
    for p in parts:
        cur = f"{cur}/{p}"
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                pass


def _put_file(sftp, local: Path, remote: str):
    remote_dir = os.path.dirname(remote).replace("\\", "/")
    _mkdir_p(sftp, remote_dir)
    sftp.put(str(local), remote)


def _git_changed_files() -> List[str]:
    """获取 git status --short 中的文件相对路径列表（含未跟踪文件）。"""
    p = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(LOCAL_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if p.returncode != 0:
        print(f"[git] ERROR: {p.stderr}")
        return []
    files: List[str] = []
    for line in p.stdout.splitlines():
        if not line.strip():
            continue
        # 形如 " M path/to/file" 或 "?? path"
        status = line[:2]
        rest = line[3:].strip()
        # 去掉首尾的双引号（带特殊字符的路径会被 git 引号包裹）
        if rest.startswith('"') and rest.endswith('"'):
            rest = rest[1:-1]
        # 重命名 "old -> new" 取 new
        if " -> " in rest:
            rest = rest.split(" -> ")[-1].strip()
        files.append(rest)
    return files


def _should_include(rel: str) -> bool:
    rel_n = rel.replace("\\", "/")
    base = os.path.basename(rel_n)
    # 排除 user_docs/、apk_、ipa_ 等前缀
    for pref in EXCLUDE_PREFIXES:
        if rel_n.startswith(pref):
            return False
    # 排除根目录下 _xxx 临时脚本
    if "/" not in rel_n and base.startswith("_"):
        return False
    # 排除 .md / .txt
    if rel_n.endswith(EXCLUDE_SUFFIX):
        return False
    return True


def upload_changes(cli, sftp, remote_root: str) -> Tuple[int, int]:
    files = _git_changed_files()
    print(f"[git] total git status entries: {len(files)}")
    uploaded = 0
    skipped = 0
    for rel in files:
        if not _should_include(rel):
            print(f"  [skip-rule] {rel}")
            skipped += 1
            continue
        local = LOCAL_ROOT / rel
        if not local.exists():
            print(f"  [skip-nofile] {rel}")
            skipped += 1
            continue
        if not local.is_file():
            print(f"  [skip-notfile] {rel}")
            skipped += 1
            continue
        remote = f"{remote_root}/{rel}".replace("\\", "/")
        try:
            _put_file(sftp, local, remote)
            uploaded += 1
            print(f"  [uploaded] {rel}")
        except Exception as e:
            print(f"  [ERR] {rel}: {e}")
            skipped += 1
    return uploaded, skipped


def rebuild_frontends(cli, remote_root: str) -> bool:
    """重建并重启 h5-web 和 admin-web 两个前端容器。"""
    compose_file = "docker-compose.prod.yml"
    print(f"\n[docker] build --no-cache h5-web admin-web (this may take 3-8 min)")
    build_cmd = (
        f"cd {remote_root} && "
        f"docker compose -f {compose_file} build --no-cache h5-web admin-web 2>&1 | tail -n 200"
    )
    c, out, err = _run(cli, build_cmd, timeout=900)
    print(f"  build exit={c}")
    print(f"---- build output (tail) ----")
    print(out[-6000:])
    if err.strip():
        print(f"---- build stderr ----")
        print(err[-2000:])
    if c != 0:
        return False

    print(f"\n[docker] up -d h5-web admin-web")
    up_cmd = (
        f"cd {remote_root} && "
        f"docker compose -f {compose_file} up -d h5-web admin-web 2>&1"
    )
    c, out, err = _run(cli, up_cmd, timeout=180)
    print(f"  up exit={c}")
    print(out[-2000:])
    if err.strip():
        print(err[-1000:])
    return c == 0


def wait_healthy(cli, names: List[str], max_wait: int = 120) -> bool:
    print(f"\n[wait] wait for containers healthy/Up (max {max_wait}s)")
    deadline = time.time() + max_wait
    while time.time() < deadline:
        all_ok = True
        for name in names:
            c, out, _ = _run(
                cli,
                f"docker inspect -f '{{{{.State.Status}}}}|{{{{if .State.Health}}}}{{{{.State.Health.Status}}}}{{{{else}}}}nohealth{{{{end}}}}' {name} 2>/dev/null",
                timeout=20,
            )
            line = out.strip()
            if not line:
                all_ok = False
                continue
            status, health = (line.split("|") + ["", ""])[:2]
            if status != "running":
                all_ok = False
            elif health not in ("healthy", "nohealth", ""):
                all_ok = False
            print(f"  {name}: status={status} health={health}")
        if all_ok:
            return True
        time.sleep(5)
    return False


def reconnect_gateway(cli):
    print("\n[gateway] connect gateway to project network and reload nginx")
    _run(
        cli,
        f"docker network connect {NETWORK} gateway 2>/dev/null || true",
        timeout=30,
    )
    c, out, err = _run(cli, "docker exec gateway nginx -t 2>&1", timeout=30)
    print(f"  nginx -t exit={c}: {out.strip()[:300]} {err.strip()[:300]}")
    c, out, err = _run(cli, "docker exec gateway nginx -s reload 2>&1", timeout=30)
    print(f"  nginx reload exit={c}: {out.strip()[:200]} {err.strip()[:200]}")


def main() -> int:
    print(f"[ssh] connecting {USER}@{HOST}")
    cli = _ssh()
    try:
        remote_root = _find_remote_dir(cli)
        print(f"[remote_root] {remote_root}")

        sftp = cli.open_sftp()
        try:
            uploaded, skipped = upload_changes(cli, sftp, remote_root)
            print(f"\n[upload] done: uploaded={uploaded} skipped={skipped}")
        finally:
            sftp.close()

        ok = rebuild_frontends(cli, remote_root)
        if not ok:
            print("[FAIL] rebuild failed")
            return 1

        names = [f"{PROJECT_ID}-h5-web", f"{PROJECT_ID}-admin-web"]
        healthy = wait_healthy(cli, names, max_wait=180)
        if not healthy:
            print("[WARN] containers not fully healthy after wait")

        reconnect_gateway(cli)

        # 输出最终状态
        c, out, _ = _run(
            cli,
            f"cd {remote_root} && docker compose -f docker-compose.prod.yml ps 2>&1 | head -n 60",
            timeout=30,
        )
        print("\n---- docker compose ps ----")
        print(out)

        for n in names:
            c, out, _ = _run(cli, f"docker logs --tail 30 {n} 2>&1", timeout=20)
            print(f"\n---- {n} logs tail ----")
            print(out[-2500:])

        return 0 if healthy else 2
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
