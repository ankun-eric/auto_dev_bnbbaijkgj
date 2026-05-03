"""部署「H5 积分商城详情页『立即兑换』按钮置灰修复」到远程服务器.

Bug：H5 端 /points/product-detail 详情页底部"立即兑换"按钮始终为灰色禁用态。
根因：后端 GET /api/points/mall/items/{id} 默认 button_state="normal"，
而前端 disabled 严格绑定到 `button_state !== 'exchangeable'`，导致按钮永远 disabled。

部署内容：
1. 后端：backend/app/api/points_exchange.py（detail 接口 + 5 态判定）
2. 后端测试：backend/tests/test_points_mall_detail_button_state.py
3. 前端 H5：h5-web/src/app/points/product-detail/page.tsx
4. 部署后跑容器内 pytest（10 个新用例 + 6 个回归用例）
5. 网关验证 H5 详情页 + 后端接口可达
"""
from __future__ import annotations

import os
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_BASE = f"/home/ubuntu/{DID}"
LOCAL_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES_TO_UPLOAD = [
    "backend/app/api/points_exchange.py",
    "backend/tests/test_points_mall_detail_button_state.py",
    "h5-web/src/app/points/product-detail/page.tsx",
]


def run(client, cmd, timeout=600):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if out:
        print(out)
    if err:
        print(f"[stderr] {err}")
    return out, err


def upload_file(sftp, local: str, remote: str) -> None:
    print(f"  upload: {local} -> {remote}")
    remote_dir = "/".join(remote.split("/")[:-1])
    parts = remote_dir.split("/")
    for i in range(2, len(parts) + 1):
        d = "/".join(parts[:i])
        try:
            sftp.stat(d)
        except IOError:
            try:
                sftp.mkdir(d)
            except IOError:
                pass
    sftp.put(local, remote)


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = client.open_sftp()
    try:
        # 1) 上传文件
        for rel in FILES_TO_UPLOAD:
            local = os.path.join(LOCAL_BASE, rel.replace("/", os.sep))
            remote = f"{REMOTE_BASE}/{rel}"
            if not os.path.isfile(local):
                print(f"[skip] local file missing: {local}")
                continue
            upload_file(sftp, local, remote)

        # 2) 后端：直接 docker cp 改的 .py 文件 + 重启容器（无依赖变更，跳过 build 加速）
        backend_files = [
            ("backend/app/api/points_exchange.py", "/app/app/api/points_exchange.py"),
            (
                "backend/tests/test_points_mall_detail_button_state.py",
                "/app/tests/test_points_mall_detail_button_state.py",
            ),
        ]
        for rel, container_path in backend_files:
            run(
                client,
                f"docker cp {REMOTE_BASE}/{rel} {DID}-backend:{container_path}",
            )
        run(client, f"docker restart {DID}-backend", timeout=120)

        # 3) 前端 H5：重新 build（Next.js 改了 page.tsx 必须 rebuild）
        run(
            client,
            f"cd {REMOTE_BASE} && docker compose up -d --build h5-web",
            timeout=900,
        )

        # 4) 等待容器启动
        time.sleep(10)
        for _ in range(15):
            out, _ = run(
                client,
                f"docker ps --format '{{{{.Names}}}} {{{{.Status}}}}' "
                f"| grep {DID}-backend",
            )
            if "Up" in out:
                break
            time.sleep(5)

        # 5) 容器内跑 pytest：本次新增 + 既有回归
        run(
            client,
            (
                f"docker exec -e PYTEST_CURRENT_TEST=1 {DID}-backend "
                f"python -m pytest "
                f"tests/test_points_mall_detail_button_state.py "
                f"tests/test_points_mall_v11.py "
                f"-v --no-header"
            ),
            timeout=600,
        )

        # 6) 网关验证：H5 详情页可达 + 后端接口可达（401 表示路由通畅）
        run(
            client,
            f"curl -s -o /dev/null -w 'h5 detail page %{{http_code}}\\n' "
            f"https://newbb.test.bangbangvip.com/autodev/{DID}/points/product-detail?id=1",
        )
        run(
            client,
            f"curl -s -o /dev/null -w 'h5 mall list %{{http_code}}\\n' "
            f"https://newbb.test.bangbangvip.com/autodev/{DID}/points/mall",
        )
        run(
            client,
            f"curl -s -o /dev/null -w 'api items detail %{{http_code}}\\n' "
            f"https://newbb.test.bangbangvip.com/autodev/{DID}/api/points/mall/items/1",
        )
        run(
            client,
            f"curl -s -o /dev/null -w 'api mall list %{{http_code}}\\n' "
            f"https://newbb.test.bangbangvip.com/autodev/{DID}/api/points/mall",
        )

        # 7) 直接调一次 detail（未登录会 401，证明接口可达）
        run(
            client,
            f"curl -s 'https://newbb.test.bangbangvip.com/autodev/{DID}/api/points/mall/items/1' | head -c 300",
        )

    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
