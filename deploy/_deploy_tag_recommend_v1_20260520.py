"""[PRD-TAG-RECOMMEND-V1 2026-05-20] 标签管理 + 问卷推荐配置 + Bug1 修复 + 履约方式正名 部署脚本

改动范围：
- 【backend】
  - 新增 backend/app/api/tag_recommend.py（标签 / 商品-标签 / 推荐配置 API）
  - 新增 backend/app/schemas/tag_recommend.py
  - 新增 backend/app/services/prd_tag_recommend_v1_migration.py（建表 + 模板加 4 列 + 体质标签 seed）
  - 改 backend/app/models/models.py（QuestionnaireTemplate +4 字段；新增 Tag / GoodsTag / QuestionnaireRecommendConfig）
  - 改 backend/app/schemas/questionnaire.py（4 个新字段）
  - 改 backend/app/api/questionnaire.py（/submit 接口返回 recommend_goods / 三段式配置）
  - 改 backend/app/main.py（注册路由 + 注册迁移）
  - 新增 backend/tests/test_tag_recommend_v1_20260520.py（14 个 TC）
- 【admin-web】
  - 改 admin-web/src/utils/fulfillmentLabel.ts（virtual=权益服务 / delivery=实物配送）
  - 改 admin-web/src/app/(admin)/layout.tsx（菜单加「标签管理」入口）
  - 新增 admin-web/src/app/(admin)/product-system/tags/page.tsx（标签管理后台）
  - 改 admin-web/src/app/(admin)/function-buttons/page.tsx（Bug1：失败提示 + 重试入口）
  - 改 admin-web/src/app/(admin)/questionnaire-templates/page.tsx（4 个新字段 + 关联推荐 Tab）
  - 改 admin-web/src/app/(admin)/points/mall/page.tsx + ProductPickerModal（文案正名）
- 【h5-web】
  - 改 h5-web/src/utils/fulfillmentLabel.ts
  - 改 h5-web/src/app/product/[id]/page.tsx
  - 新增 h5-web/src/components/ai-chat/QuestionnaireRecommendCard.tsx
  - 新增 h5-web/src/components/ai-chat/RecommendGoodsDrawer.tsx
  - 改 h5-web/src/app/(ai-chat)/ai-home/page.tsx（三段式 UI 集成）
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
    # backend - 新增 API
    ("backend/app/api/tag_recommend.py",
     "backend/app/api/tag_recommend.py"),
    ("backend/app/schemas/tag_recommend.py",
     "backend/app/schemas/tag_recommend.py"),
    ("backend/app/services/prd_tag_recommend_v1_migration.py",
     "backend/app/services/prd_tag_recommend_v1_migration.py"),
    # backend - 改 ORM / schemas / API / main
    ("backend/app/models/models.py", "backend/app/models/models.py"),
    ("backend/app/schemas/questionnaire.py",
     "backend/app/schemas/questionnaire.py"),
    ("backend/app/api/questionnaire.py", "backend/app/api/questionnaire.py"),
    ("backend/app/main.py", "backend/app/main.py"),
    # backend - tests
    ("backend/tests/test_tag_recommend_v1_20260520.py",
     "backend/tests/test_tag_recommend_v1_20260520.py"),
    # admin-web
    ("admin-web/src/utils/fulfillmentLabel.ts",
     "admin-web/src/utils/fulfillmentLabel.ts"),
    ("admin-web/src/app/(admin)/layout.tsx",
     "admin-web/src/app/(admin)/layout.tsx"),
    ("admin-web/src/app/(admin)/product-system/tags/page.tsx",
     "admin-web/src/app/(admin)/product-system/tags/page.tsx"),
    ("admin-web/src/app/(admin)/function-buttons/page.tsx",
     "admin-web/src/app/(admin)/function-buttons/page.tsx"),
    ("admin-web/src/app/(admin)/questionnaire-templates/page.tsx",
     "admin-web/src/app/(admin)/questionnaire-templates/page.tsx"),
    ("admin-web/src/app/(admin)/points/mall/page.tsx",
     "admin-web/src/app/(admin)/points/mall/page.tsx"),
    ("admin-web/src/components/coupon/ProductPickerModal.tsx",
     "admin-web/src/components/coupon/ProductPickerModal.tsx"),
    # h5-web
    ("h5-web/src/utils/fulfillmentLabel.ts",
     "h5-web/src/utils/fulfillmentLabel.ts"),
    ("h5-web/src/app/product/[id]/page.tsx",
     "h5-web/src/app/product/[id]/page.tsx"),
    ("h5-web/src/components/ai-chat/QuestionnaireRecommendCard.tsx",
     "h5-web/src/components/ai-chat/QuestionnaireRecommendCard.tsx"),
    ("h5-web/src/components/ai-chat/RecommendGoodsDrawer.tsx",
     "h5-web/src/components/ai-chat/RecommendGoodsDrawer.tsx"),
    ("h5-web/src/app/(ai-chat)/ai-home/page.tsx",
     "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
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

        # 拷贝 backend 源进容器并重启
        print("\n--- 同步 backend 源到容器 ---")
        backend_files = [
            "backend/app/api/tag_recommend.py",
            "backend/app/schemas/tag_recommend.py",
            "backend/app/services/prd_tag_recommend_v1_migration.py",
            "backend/app/models/models.py",
            "backend/app/schemas/questionnaire.py",
            "backend/app/api/questionnaire.py",
            "backend/app/main.py",
            "backend/tests/test_tag_recommend_v1_20260520.py",
        ]
        for rel in backend_files:
            inner = "/app/" + rel.replace("backend/", "", 1)
            run(client, f"docker exec {backend_container} mkdir -p '{os.path.dirname(inner)}'",
                ignore_err=True, show=False)
            run(client,
                f"docker cp '{PROJ_DIR}/{rel}' '{backend_container}:{inner}' 2>&1",
                ignore_err=True, show=False)

        print("\n--- restart backend ---")
        run(client,
            f"cd {PROJ_DIR} && docker compose -f {compose_file} restart backend 2>&1 | tail -3",
            ignore_err=True)
        # 等待启动
        print("等待 backend 就绪 + 跑迁移...")
        for i in range(40):
            time.sleep(3)
            rc, out, _ = run(
                client,
                f"docker logs --tail 80 {backend_container} 2>&1",
                ignore_err=True, show=False,
            )
            if "prd_tag_recommend_v1: 迁移完成" in out:
                print("  迁移完成。")
                break
            if "Uvicorn running" in out and i >= 5:
                print("  backend 启动完成（迁移日志可能已滚出，继续）")
                break

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
            f"{BASE_URL}/admin/product-system/tags",
            f"{BASE_URL}/admin/function-buttons",
            f"{BASE_URL}/admin/questionnaire-templates",
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

        # 把 h5-web 和 admin-web 源码 docker cp 进 backend 容器，便于 pytest 校验
        print("\n--- 同步前端源码到 backend 容器（供 pytest 源码校验）---")
        front_src = [
            "backend/app/services/prd_tag_recommend_v1_migration.py",
            "h5-web/src/utils/fulfillmentLabel.ts",
            "h5-web/src/app/product/[id]/page.tsx",
            "h5-web/src/components/ai-chat/QuestionnaireRecommendCard.tsx",
            "h5-web/src/components/ai-chat/RecommendGoodsDrawer.tsx",
            "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
            "admin-web/src/utils/fulfillmentLabel.ts",
            "admin-web/src/app/(admin)/layout.tsx",
            "admin-web/src/app/(admin)/product-system/tags/page.tsx",
            "admin-web/src/app/(admin)/function-buttons/page.tsx",
            "admin-web/src/app/(admin)/questionnaire-templates/page.tsx",
        ]
        for rel in front_src:
            target_in_container = f"/app/{rel}"
            target_dir = os.path.dirname(target_in_container)
            run(client, f"docker exec {backend_container} mkdir -p '{target_dir}'",
                ignore_err=True, show=False)
            run(client,
                f"docker cp '{PROJ_DIR}/{rel}' '{backend_container}:{target_in_container}' 2>&1",
                ignore_err=True, show=False)

        # 远端 pytest
        print("\n--- backend 容器内 pytest 执行 ---")
        rc, out, _ = run(
            client,
            f"docker exec {backend_container} python -m pytest "
            f"tests/test_tag_recommend_v1_20260520.py -v --tb=short --no-header 2>&1 | tail -80",
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
