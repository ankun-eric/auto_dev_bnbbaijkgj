"""[PRD-AI-HOME-OPTIM-FINAL-V2 2026-05-19] AI 首页优化最终版 部署脚本

改动范围（仅 H5 端）：
- h5-web/src/components/ai-chat/ConsultTargetPicker.tsx：
  - 标题：「咨询人」→「选择咨询人」
  - 选中条统一蓝色渐变背景（不论本人/家人）
  - 未选中条统一浅灰底（本人不再有「天生蓝底」特权）
  - 主标题统一「关系 · 姓名」格式
  - 右侧文字按钮：未选中态「选择」实心蓝底白字；选中态「已选择」白底蓝字 + 禁用
- h5-web/src/app/(ai-chat)/ai-home/page.tsx：
  - 输入框 placeholder 动态化：「问答已结合【XX】的健康档案~」
  - 麦克风/键盘 SVG 图标复用 ./chat 资源（描边色改白）+ 圆形渐变蓝底容器
  - 整条输入栏外层背景透明
  - 「按住说话」按钮 #0EA5E9 实底 + 白字 + 圆角 16px + 高度 40px

后端无任何代码改动；新增前端源码校验测试：
- backend/tests/test_ai_home_optim_final_v2_20260519.py（12 个 TC）
"""
from __future__ import annotations

import os
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

FILES = [
    # H5-web 改动
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    ("h5-web/src/components/ai-chat/ConsultTargetPicker.tsx",
     "h5-web/src/components/ai-chat/ConsultTargetPicker.tsx"),
    # 后端测试（前端源码校验）
    ("backend/tests/test_ai_home_optim_final_v2_20260519.py",
     "backend/tests/test_ai_home_optim_final_v2_20260519.py"),
]


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:240]}{'...' if len(cmd) > 240 else ''}", flush=True)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 60, get_pty=False)
    stdout.channel.settimeout(timeout + 60)
    stderr.channel.settimeout(timeout + 60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-3000:], flush=True)
    if show and err.strip():
        print("STDERR:", err[-1500:], flush=True)
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}\n{err}")
    return rc, out, err


def main():
    base = os.path.abspath(os.path.dirname(__file__) + "/..")
    print(f"Local base: {base}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}:{PORT}...")
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    print("Connected.")

    try:
        sftp = client.open_sftp()
        for local_rel, remote_rel in FILES:
            local_abs = os.path.join(base, local_rel.replace("/", os.sep))
            if not os.path.exists(local_abs):
                print(f"  [SKIP] missing local: {local_abs}")
                continue
            remote_abs = f"{PROJ_DIR}/{remote_rel}"
            run(client, f"mkdir -p '{os.path.dirname(remote_abs)}'", show=False)
            print(f"  upload: {local_rel} -> {remote_abs}")
            sftp.put(local_abs, remote_abs)
        sftp.close()

        backend_container = f"{DEPLOY_ID}-backend"
        h5_container = f"{DEPLOY_ID}-h5"

        rc, out, _ = run(client, f"ls {PROJ_DIR}/docker-compose*.yml 2>&1",
                         ignore_err=True, show=False)
        print("compose files:", out.strip())
        compose_file = "docker-compose.prod.yml" if "docker-compose.prod.yml" in out else "docker-compose.yml"

        # 同步 backend 测试到容器（h5-web 源码 mount 通常已通过 build 复制；前端校验测试需读取 h5-web 文件）
        print("\n--- 同步 backend 测试到容器 ---")
        # 测试需要读 h5-web/，所以确认容器内 /app 工作目录
        # 但 backend 容器一般无 h5-web 源；测试已通过 pytest.mark.skipif 兜底
        # 这里把测试拷进去仅用于执行 skip 逻辑
        run(
            client,
            f"docker cp {PROJ_DIR}/backend/tests/test_ai_home_optim_final_v2_20260519.py "
            f"{backend_container}:/app/tests/test_ai_home_optim_final_v2_20260519.py 2>&1",
            ignore_err=True,
        )

        # 重建 h5-web
        print("\n--- rebuild h5-web ---")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} stop h5-web 2>&1 | tail -3",
            ignore_err=True)
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} rm -f h5-web 2>&1 | tail -3",
            ignore_err=True)
        print("Building h5-web (5-10 min)...")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} build h5-web 2>&1 | tail -120",
            timeout=1800)
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} up -d h5-web 2>&1 | tail -10")

        # 等 h5-web
        print("\n--- 等待 h5-web 就绪 ---")
        for i in range(80):
            rc, out, _ = run(
                client,
                "docker inspect --format='{{.State.Status}}' " + h5_container + " 2>&1",
                ignore_err=True, show=False,
            )
            s = out.strip()
            print(f"  [{(i + 1) * 5}s] h5-web: {s}")
            if s == "running":
                rc2, out2, _ = run(
                    client,
                    f"docker logs --tail 60 {h5_container} 2>&1 | tail -30",
                    ignore_err=True, show=False,
                )
                if "Ready in" in out2 or "Local:" in out2 or "started server" in out2 \
                        or "Listening on" in out2:
                    print("  h5-web ready.")
                    break
            time.sleep(5)

        # smoke
        print("\n--- smoke 测试 ---")
        smoke_urls = [
            f"{BASE_URL}/api/openapi.json",
            f"{BASE_URL}/ai-home",
            f"{BASE_URL}/",
        ]
        smoke_results = []
        for url in smoke_urls:
            rc, out, _ = run(
                client,
                f"curl -ks -o /dev/null -w '%{{http_code}}' '{url}' || echo curl-fail",
                ignore_err=True, show=False,
            )
            code = out.strip()
            print(f"  {url} -> {code}")
            smoke_results.append((url, code))

        # 校验已部署的 h5-web 容器内确实包含新代码标识
        print("\n--- 容器内代码校验 ---")
        markers = [
            ("ConsultTargetPicker.tsx", "选择咨询人", "标题改名"),
            ("ConsultTargetPicker.tsx", "consult-target-select-btn", "「选择」按钮"),
            ("ConsultTargetPicker.tsx", "consult-target-selected-btn", "「已选择」标签"),
            ("ai-home/page.tsx", "问答已结合", "动态 placeholder"),
            ("ai-home/page.tsx", "ai-home-press-to-talk", "「按住说话」按钮"),
            ("ai-home/page.tsx", "ai-home-input-icon-btn", "麦克风/键盘 圆底按钮"),
        ]
        # h5-web Next.js 容器内源码路径通常是 /app/src/...
        for fname, marker, desc in markers:
            grep_cmd = (
                f"docker exec {h5_container} sh -c \""
                f"grep -r --include='*.tsx' -l '{marker}' /app/src 2>/dev/null | head -3\""
            )
            rc, out, _ = run(client, grep_cmd, ignore_err=True, show=False)
            hit = out.strip()
            mark = "OK" if hit else "MISS"
            print(f"  [{mark}] {desc} | marker={marker!r} -> {hit or '(none)'}")

        # 远端 pytest（在 backend 容器执行；因 h5-web 不在 backend 容器中，测试会 skip）
        # 但更有意义的方式：在本地（部署服务器上）通过 docker exec h5-web 容器跑测试
        # 这里通过把仓库根目录 + python 直接跑 pytest（如服务器有 python3 + pytest）
        print("\n--- 远端前端源码 pytest（基于服务器仓库 h5-web/ 源文件） ---")
        # 服务器上 PROJ_DIR 下应有完整的 h5-web 源文件（部署时 SFTP 上传过），
        # 因此用 backend 容器跑测试，但临时把 h5-web 目录挂载/复制进容器是过度设计；
        # 更简单：用 backend 容器跑 pytest，conftest 里 pytestmark skipif 会自动 skip。
        # 同时我们额外用一种轻量方式：在服务器宿主机（如果有 python3）直接跑 pytest。
        # 优先方案：把 h5-web 必要文件 docker cp 进 backend 容器后再跑。
        for h5_rel in [
            "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
            "h5-web/src/components/ai-chat/ConsultTargetPicker.tsx",
        ]:
            target_in_container = f"/app/{h5_rel}"
            target_dir = os.path.dirname(target_in_container)
            run(
                client,
                f"docker exec {backend_container} mkdir -p '{target_dir}'",
                ignore_err=True, show=False,
            )
            # 服务器路径 = PROJ_DIR/{h5_rel}
            run(
                client,
                f"docker cp '{PROJ_DIR}/{h5_rel}' "
                f"'{backend_container}:{target_in_container}' 2>&1",
                ignore_err=True, show=False,
            )

        # backend 容器内测试用到 REPO_ROOT = parents[2]，即 /app/tests/x.py -> /app
        # 而 H5_AI_HOME = REPO_ROOT/h5-web/src/app/(ai-chat)/ai-home/page.tsx = /app/h5-web/...
        # 上面 docker cp 已把 h5-web 源放到 /app/h5-web/...，所以测试应能解析到。
        print("\n--- backend 容器内 pytest 执行 ---")
        rc, out, _ = run(
            client,
            f"docker exec {backend_container} python -m pytest "
            f"tests/test_ai_home_optim_final_v2_20260519.py -v --tb=short --no-header 2>&1 | tail -100",
            ignore_err=True,
            timeout=300,
        )

        pytest_summary = ""
        for line in out.splitlines()[-15:]:
            if "passed" in line or "failed" in line or "error" in line.lower():
                pytest_summary = line.strip()

        print("\n========== 部署摘要 ==========")
        print(f"基础 URL: {BASE_URL}")
        print("smoke:")
        for u, c in smoke_results:
            print(f"  {c}  {u}")
        print(f"pytest: {pytest_summary or '(see above)'}")
        print("==============================")

    finally:
        client.close()
        print("Done.")


if __name__ == "__main__":
    main()
