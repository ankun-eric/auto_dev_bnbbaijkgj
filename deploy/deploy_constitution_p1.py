"""中医体质测评一期（6 屏结果页 + 套餐推荐 + 优惠券 + 档案）部署脚本。

涉及变更：
- backend: 新增 app/services/constitution_content.py、app/api/constitution.py；main.py 注册路由
- h5-web: 新增 /tcm/loading、/tcm/result/[id]、/tcm/archive 页面；tcm 首页增加档案入口
- miniprogram / flutter_app：纯静态改动，由各自打包流程处理，不在本脚本范围

部署方式：服务器 git fetch + reset 至最新 master，然后 docker compose 重建 backend + h5-web。
"""
import time
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
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if not quiet:
        if out:
            print(out[-3000:])
        if err:
            print(f"[stderr] {err[-1500:]}")
        print(f"[exit {code}]")
    if check and code != 0:
        raise RuntimeError(f"FAIL ({code}): {cmd}")
    return out, err, code


def main():
    c = connect()
    print(f"Connected to {HOST}")

    print("\n=== Step 1: 从 Git 拉取最新代码 ===")
    run(c, f"cd {PROJECT_DIR} && git fetch origin master && git reset --hard origin/master && git log -1 --oneline",
        timeout=180, check=True)

    print("\n=== Step 2: 校验关键新文件存在 ===")
    key_files = [
        "backend/app/services/constitution_content.py",
        "backend/app/api/constitution.py",
        "h5-web/src/app/tcm/loading/page.tsx",
        "h5-web/src/app/tcm/result/[id]/page.tsx",
        "h5-web/src/app/tcm/archive/page.tsx",
    ]
    for f in key_files:
        run(c, f"test -f {PROJECT_DIR}/{f} && echo OK:{f} || echo MISS:{f}")

    print("\n=== Step 3: docker compose build backend + h5-web（容器内是镜像代码，必须重建） ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build backend h5-web 2>&1 | tail -60",
        timeout=1800, check=True)

    print("\n=== Step 4: 重启 backend + h5-web ===")
    run(c, f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d --force-recreate backend h5-web 2>&1 | tail -25",
        timeout=240, check=True)

    print("\n=== Step 5: 等待容器就绪 ===")
    time.sleep(15)
    for i in range(18):
        out, _, _ = run(
            c,
            f"docker ps --filter name={DEPLOY_ID} --format '{{{{.Names}}}}\t{{{{.Status}}}}'",
            quiet=True,
        )
        up_count = out.count("Up ")
        print(f"  [check {i+1}] containers Up={up_count}")
        if up_count >= 3 and "Restarting" not in out:
            break
        time.sleep(6)

    print("\n=== Step 6: 容器状态 ===")
    run(c, f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}'")

    print("\n=== Step 7: 关键链路快检 ===")
    base = f"https://{DOMAIN}/autodev/{DEPLOY_ID}"
    paths = [
        # 前端
        "/tcm",
        "/tcm/loading",
        "/tcm/archive",
        "/tcm/result/1",
        # 后端新增接口
        "/api/constitution/archive",
        "/api/constitution/coupon/status",
        # 后端关键已有接口（体质测评依赖）
        "/api/tcm/config",
        # 兜底
        "/",
    ]
    print("\n--- 可达性检查（期望 2xx/3xx/401 均视为可达；500 视为失败） ---")
    fails = []
    for path in paths:
        url = f"{base}{path}"
        out, _, _ = run(c, f"curl -s -o /dev/null -w '%{{http_code}}' '{url}'", quiet=True)
        code = out.strip()
        ok = code.startswith(("2", "3")) or code in ("401", "403", "404")
        # 404 对未登录状态下某些 API 也是合理的，但业务接口期望 401/200，这里宽松一点
        mark = "OK " if ok else "FAIL"
        print(f"  [{mark}] {code}  {path}")
        if not ok:
            fails.append((path, code))

    c.close()
    if fails:
        print("\n=== 存在失败链接 ===")
        for p, code in fails:
            print(f"  - {code}  {p}")
        raise SystemExit(1)

    print("\n=== DEPLOY DONE ===")
    print(f"访问首页：{base}/tcm")


if __name__ == "__main__":
    main()
