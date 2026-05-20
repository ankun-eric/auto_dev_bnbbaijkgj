"""[PRD-AICHAT-FUNCCARD-V2 2026-05-20] AI 对话页「功能引导卡片」新版样式改造 部署脚本

改动范围：
- 【H5 端】
  - 新建 h5-web/src/components/ai-chat/FunctionCardV2.tsx（统一新版卡片渲染器）
  - 改造 h5-web/src/components/ai-chat/ChatCards.tsx（Navigate/SdkCall/Upload 全量切换到 V2）
  - 改造 h5-web/src/components/ai-chat/QuestionnairePreCard.tsx（委托 V2 渲染）
  - 修改 h5-web/src/app/(ai-chat)/ai-home/page.tsx（透传 button_sub_desc → buttonSubDesc）
- 【admin-web 端】
  - 新建 admin-web/src/components/FunctionCardV2Preview.tsx（375x667 手机框 + V2 复刻）
  - 修改 admin-web/src/app/(admin)/function-buttons/page.tsx（增加"预览效果"按钮 + 浮层）
- 【backend】
  - 新增 backend/tests/test_funccard_v2_20260520.py（11 个前端源码校验 TC）

后端无任何 DB / API 改动，无新字段、无新接口、无数据迁移。
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
    # H5
    ("h5-web/src/components/ai-chat/FunctionCardV2.tsx",
     "h5-web/src/components/ai-chat/FunctionCardV2.tsx"),
    ("h5-web/src/components/ai-chat/ChatCards.tsx",
     "h5-web/src/components/ai-chat/ChatCards.tsx"),
    ("h5-web/src/components/ai-chat/QuestionnairePreCard.tsx",
     "h5-web/src/components/ai-chat/QuestionnairePreCard.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    # admin-web
    ("admin-web/src/components/FunctionCardV2Preview.tsx",
     "admin-web/src/components/FunctionCardV2Preview.tsx"),
    ("admin-web/src/app/(admin)/function-buttons/page.tsx",
     "admin-web/src/app/(admin)/function-buttons/page.tsx"),
    # backend tests
    ("backend/tests/test_funccard_v2_20260520.py",
     "backend/tests/test_funccard_v2_20260520.py"),
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
        admin_container = f"{DEPLOY_ID}-admin"

        rc, out, _ = run(client, f"ls {PROJ_DIR}/docker-compose*.yml 2>&1",
                         ignore_err=True, show=False)
        print("compose files:", out.strip())
        compose_file = "docker-compose.prod.yml" if "docker-compose.prod.yml" in out else "docker-compose.yml"

        # 重建 h5-web 和 admin-web 镜像（两端都有改动）
        for svc, cname in [("h5-web", h5_container), ("admin-web", admin_container)]:
            print(f"\n--- rebuild {svc} ---")
            run(client,
                f"cd {PROJ_DIR} && docker compose -f {compose_file} stop {svc} 2>&1 | tail -3",
                ignore_err=True)
            run(client,
                f"cd {PROJ_DIR} && docker compose -f {compose_file} rm -f {svc} 2>&1 | tail -3",
                ignore_err=True)
            print(f"Building {svc} (5-10 min)...")
            run(client,
                f"cd {PROJ_DIR} && docker compose -f {compose_file} build {svc} 2>&1 | tail -120",
                timeout=1800)
            run(client,
                f"cd {PROJ_DIR} && docker compose -f {compose_file} up -d {svc} 2>&1 | tail -10")

            print(f"--- 等待 {svc} 就绪 ---")
            for i in range(60):
                rc, out, _ = run(
                    client,
                    "docker inspect --format='{{.State.Status}}' " + cname + " 2>&1",
                    ignore_err=True, show=False,
                )
                s = out.strip()
                if (i + 1) % 4 == 0:
                    print(f"  [{(i + 1) * 5}s] {svc}: {s}")
                if s == "running":
                    rc2, out2, _ = run(
                        client,
                        f"docker logs --tail 60 {cname} 2>&1 | tail -30",
                        ignore_err=True, show=False,
                    )
                    if any(k in out2 for k in ["Ready in", "Local:", "started server", "Listening on"]):
                        print(f"  {svc} ready.")
                        break
                time.sleep(5)

        # smoke 验证
        print("\n--- smoke 测试 ---")
        smoke_urls = [
            f"{BASE_URL}/api/openapi.json",
            f"{BASE_URL}/ai-home",
            f"{BASE_URL}/",
            f"{BASE_URL}/admin/function-buttons",
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

        # 容器内代码校验：h5-web 和 admin-web 镜像里都存在新关键字
        print("\n--- 容器内代码校验 ---")
        markers = [
            (h5_container, "FunctionCardV2.tsx", "function-card-v2", "H5 V2 卡片组件"),
            (h5_container, "ChatCards.tsx", "FunctionCardV2", "H5 ChatCards 接入 V2"),
            (h5_container, "QuestionnairePreCard.tsx", "FunctionCardV2", "H5 QnPreCard 接入 V2"),
            (admin_container, "FunctionCardV2Preview.tsx", "function-card-v2-preview", "Admin 预览组件"),
            (admin_container, "function-buttons", "function-card-preview-trigger", "Admin 预览触发按钮"),
        ]
        for cname, fname, marker, desc in markers:
            grep_cmd = (
                f"docker exec {cname} sh -c \""
                f"grep -r --include='*.tsx' -l '{marker}' /app/src 2>/dev/null | head -3\""
            )
            rc, out, _ = run(client, grep_cmd, ignore_err=True, show=False)
            hit = out.strip()
            mark = "OK" if hit else "MISS"
            print(f"  [{mark}] {desc} | marker={marker!r} -> {hit or '(none)'}")

        # 把 h5-web 和 admin-web 源码 docker cp 进 backend 容器，便于 pytest 校验
        print("\n--- 同步前端源码到 backend 容器 ---")
        h5_src = [
            "h5-web/src/components/ai-chat/FunctionCardV2.tsx",
            "h5-web/src/components/ai-chat/ChatCards.tsx",
            "h5-web/src/components/ai-chat/QuestionnairePreCard.tsx",
            "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
        ]
        admin_src = [
            "admin-web/src/components/FunctionCardV2Preview.tsx",
            "admin-web/src/app/(admin)/function-buttons/page.tsx",
        ]
        for rel in h5_src + admin_src:
            target_in_container = f"/app/{rel}"
            target_dir = os.path.dirname(target_in_container)
            run(client, f"docker exec {backend_container} mkdir -p '{target_dir}'",
                ignore_err=True, show=False)
            run(client,
                f"docker cp '{PROJ_DIR}/{rel}' '{backend_container}:{target_in_container}' 2>&1",
                ignore_err=True, show=False)

        # 同步本次测试到容器
        run(client,
            f"docker cp {PROJ_DIR}/backend/tests/test_funccard_v2_20260520.py "
            f"{backend_container}:/app/tests/test_funccard_v2_20260520.py 2>&1",
            ignore_err=True)

        # 远端 pytest
        print("\n--- backend 容器内 pytest 执行 ---")
        rc, out, _ = run(
            client,
            f"docker exec {backend_container} python -m pytest "
            f"tests/test_funccard_v2_20260520.py -v --tb=short --no-header 2>&1 | tail -60",
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
