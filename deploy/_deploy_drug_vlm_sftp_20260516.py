"""[BUG_FIX_用药识别千图一答 2026-05-16] SFTP 旁路部署脚本

服务器到 GitHub 的网络极慢（git fetch 经常 1KB/s 超时）。本脚本绕过 GitHub：
直接通过 SFTP 把本地改动文件推到服务器对应路径，然后重建 backend 容器即可。

涉及文件（与本次 commit 一致）：
- backend/app/api/drug.py
- backend/app/services/ai_service.py
- backend/scripts/cleanup_legacy_drug_identify.py
- backend/tests/test_drug_identify_vlm_20260516.py
- deploy/_test_drug_vlm_server_20260516.py（可选）
"""
import os
import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
GATEWAY = "gateway"
SERVICE = "backend"
CONTAINER = f"{DEPLOY_ID}-backend"

LOCAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES_TO_UPLOAD = [
    "backend/app/api/drug.py",
    "backend/app/services/ai_service.py",
    "backend/scripts/cleanup_legacy_drug_identify.py",
    "backend/tests/test_drug_identify_vlm_20260516.py",
]


def run(client, cmd, timeout=600, ignore_err=False, show=True):
    if show:
        print(f"\n$ {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if show and out.strip():
        print(out[-3000:])
    if show and err.strip():
        print("STDERR:", err[-2000:])
    if rc != 0 and not ignore_err:
        raise RuntimeError(f"cmd failed (rc={rc}): {cmd[:120]}\n{err}")
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}:{PORT}...")
    client.connect(
        HOST,
        port=PORT,
        username=USER,
        password=PWD,
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )
    print("Connected.")

    sftp = client.open_sftp()
    try:
        # 1. 上传文件（先确保目录存在）
        for rel in FILES_TO_UPLOAD:
            local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
            remote = f"{PROJ_DIR}/{rel}"
            if not os.path.exists(local):
                print(f"[SKIP] local missing: {local}")
                continue
            # 确保目录存在
            remote_dir = os.path.dirname(remote)
            run(client, f"mkdir -p {remote_dir}", ignore_err=True, show=False)
            print(f"[UPLOAD] {rel} ({os.path.getsize(local)} bytes)")
            sftp.put(local, remote)

        # 2. 校验上传成功
        run(
            client,
            f"cd {PROJ_DIR} && ls -la "
            + " ".join(FILES_TO_UPLOAD)
            + " 2>&1",
        )
        run(
            client,
            f"cd {PROJ_DIR} && grep -c 'identify_drug_structured\\|build_vision_message_content' "
            "backend/app/services/ai_service.py",
            ignore_err=True,
        )

        # 3. 重建 backend
        run(
            client,
            f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml stop {SERVICE} 2>&1 | tail -3",
            ignore_err=True,
        )
        run(
            client,
            f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml rm -f {SERVICE} 2>&1 | tail -3",
            ignore_err=True,
        )
        print("\nBuilding backend with --no-cache ...")
        run(
            client,
            f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml build --no-cache {SERVICE} 2>&1 | tail -40",
            timeout=900,
        )
        run(
            client,
            f"cd {PROJ_DIR} && docker compose -f docker-compose.prod.yml up -d {SERVICE} 2>&1 | tail -10",
        )

        # 4. 等就绪
        print("\n--- Waiting for backend ---")
        ready = False
        for i in range(36):
            rc, out, _ = run(
                client,
                "docker inspect --format='{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}' "
                + CONTAINER,
                ignore_err=True,
                show=False,
            )
            status = out.strip()
            print(f"  [{(i + 1) * 5}s] backend: {status}")
            if status.startswith("running|"):
                health = status.split("|", 1)[1] if "|" in status else ""
                if health == "" or health == "healthy":
                    ready = True
                    break
            time.sleep(5)
        if not ready:
            print("WARNING: backend did not become ready within 180s")

        # 5. 容器内代码确认（grep 出关键标识）
        run(
            client,
            f"docker exec {CONTAINER} sh -c 'grep -c \"identify-v2\" /app/app/api/drug.py' 2>&1",
            ignore_err=True,
        )
        run(
            client,
            f"docker exec {CONTAINER} sh -c 'grep -c \"build_vision_message_content\\|identify_drug_structured\" /app/app/services/ai_service.py' 2>&1",
            ignore_err=True,
        )

        # 6. gateway reload
        run(client, f"docker exec {GATEWAY} nginx -t 2>&1")
        run(
            client,
            f"docker exec {GATEWAY} nginx -s reload 2>&1",
            ignore_err=True,
        )

        # 7. 状态
        run(
            client,
            f"docker ps --filter name={DEPLOY_ID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'",
        )

        # 8. 测试 /api/drugs/identify-v2 路由是否存在（用 HEAD 或 GET 探测，没鉴权应 401/422/405，不是 404）
        run(
            client,
            f"docker exec {CONTAINER} sh -c 'python -c \""
            "import urllib.request,urllib.error; "
            "url=\\\"http://localhost:8000/api/drugs/identify-v2\\\"; "
            "try: urllib.request.urlopen(url, timeout=5); print(\\\"GET 200\\\")"
            "\n"
            "except urllib.error.HTTPError as e: print(\\\"GET\\\", e.code)\""
            "' 2>&1",
            ignore_err=True,
        )
        run(
            client,
            f"docker exec {CONTAINER} sh -c 'python -c \""
            "import urllib.request,urllib.error; "
            "url=\\\"http://localhost:8000/api/drugs/identify\\\"; "
            "try: urllib.request.urlopen(url, timeout=5); print(\\\"GET 200\\\")"
            "\n"
            "except urllib.error.HTTPError as e: print(\\\"GET\\\", e.code)\""
            "' 2>&1",
            ignore_err=True,
        )

        print("\n[SFTP DEPLOY DONE]")
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
