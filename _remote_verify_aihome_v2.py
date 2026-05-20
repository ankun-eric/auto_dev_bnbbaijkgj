"""[PRD-AI-HOME-OPTIM-FINAL-V2] 仅做远端测试再校验：
1) 同步更新后的测试文件
2) 重新 docker cp h5-web 源到 backend 容器 /app/h5-web/
3) 在 backend 容器内跑 pytest
"""
from __future__ import annotations

import os
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ_DIR = f"/home/ubuntu/{DEPLOY_ID}"
BACKEND_CONTAINER = f"{DEPLOY_ID}-backend"


def run(client, cmd, ignore=False, timeout=300):
    print(f"$ {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 30)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out[-2000:])
    if err.strip():
        print("STDERR:", err[-800:])
    if rc != 0 and not ignore:
        raise RuntimeError(f"rc={rc}")
    return rc, out, err


def main():
    base = os.path.abspath(os.path.dirname(__file__))

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30,
                   allow_agent=False, look_for_keys=False)
    try:
        sftp = client.open_sftp()
        local_test = os.path.join(base, "backend", "tests",
                                  "test_ai_home_optim_final_v2_20260519.py")
        remote_test = f"{PROJ_DIR}/backend/tests/test_ai_home_optim_final_v2_20260519.py"
        print(f"upload {local_test} -> {remote_test}")
        sftp.put(local_test, remote_test)
        sftp.close()

        run(client,
            f"docker cp {remote_test} {BACKEND_CONTAINER}:/app/tests/test_ai_home_optim_final_v2_20260519.py",
            ignore=True)

        # 确保容器内 h5-web 源文件最新（再 cp 一次）
        for rel in [
            "h5-web/src/app/(ai-chat)/ai-home/page.tsx",
            "h5-web/src/components/ai-chat/ConsultTargetPicker.tsx",
        ]:
            target = f"/app/{rel}"
            target_dir = os.path.dirname(target)
            run(client, f"docker exec {BACKEND_CONTAINER} mkdir -p '{target_dir}'", ignore=True)
            # 用 sh -c 包裹来正确处理路径中的圆括号
            run(client,
                f"docker cp '{PROJ_DIR}/{rel}' '{BACKEND_CONTAINER}:{target}'",
                ignore=True)

        run(client,
            f"docker exec {BACKEND_CONTAINER} ls '/app/h5-web/src/app/(ai-chat)/ai-home/page.tsx' "
            f"'/app/h5-web/src/components/ai-chat/ConsultTargetPicker.tsx' 2>&1",
            ignore=True)

        # 跑 pytest
        rc, out, _ = run(client,
            f"docker exec {BACKEND_CONTAINER} python -m pytest "
            f"tests/test_ai_home_optim_final_v2_20260519.py -v --tb=long --no-header 2>&1 | tail -80",
            ignore=True, timeout=300)
        print("=== pytest done ===")
    finally:
        client.close()


if __name__ == "__main__":
    main()
