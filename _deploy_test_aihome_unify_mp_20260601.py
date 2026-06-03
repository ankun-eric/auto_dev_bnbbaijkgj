"""[PRD-AIHOME-UNIFY-V1 2026-06-01] 阶段2 部署与服务器测试辅助脚本（小程序端 + 后端测试）

本次需求 H5 两版已提前实现并部署上线（线上 HTML 已含统一顶栏 + 模式胶囊）。
本会话改动：小程序两版（6 文件）+ 后端测试（1 文件）+ 兼容旧测试（1 文件）。
小程序非容器化（阶段4 打 zip），此处只需：
  1) 把更新后的小程序源码 + 新测试文件上传到服务器项目目录
  2) docker cp 把 h5-web / miniprogram 拷进 backend 容器根目录（满足测试 _ROOT 布局）
  3) 容器内 pytest 跑两套 AI 首页测试，输出结果
"""
import os
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"
BACKEND = f"{DEPLOY_ID}-backend"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FILES = [
    "miniprogram/pages/ai/index.wxml",
    "miniprogram/pages/ai/index.js",
    "miniprogram/pages/ai/index.wxss",
    "miniprogram/pages/care-ai-home/index.wxml",
    "miniprogram/pages/care-ai-home/index.js",
    "miniprogram/pages/care-ai-home/index.wxss",
    "backend/tests/test_ai_home_unify_v1_20260601.py",
    "backend/tests/test_ai_home_mode_capsule_v1_20260531.py",
]


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = cli.open_sftp()

    # 1. 上传文件
    for rel in UPLOAD_FILES:
        local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
        remote = f"{REMOTE_ROOT}/{rel}"
        # 确保远端目录存在
        rdir = os.path.dirname(remote)
        cli.exec_command(f"mkdir -p {rdir}")[1].channel.recv_exit_status()
        sftp.put(local, remote)
        print(f"[upload] {rel}")
    sftp.close()

    def run(cmd, timeout=600):
        _in, out, err = cli.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        c = out.channel.recv_exit_status()
        return c, o, e

    # 2. docker cp h5-web / miniprogram 进容器根目录（满足测试 _ROOT=/ 布局）
    print("\n--- docker cp 源码进 backend 容器 ---")
    for d in ("h5-web", "miniprogram"):
        run(f"docker exec {BACKEND} rm -rf /{d}")
        c, o, e = run(f"docker cp {REMOTE_ROOT}/{d} {BACKEND}:/{d}", timeout=300)
        print(f"docker cp {d}: exit={c} {e.strip()[:200]}")
    # 测试文件拷进 /app/tests
    for t in ("test_ai_home_unify_v1_20260601.py", "test_ai_home_mode_capsule_v1_20260531.py"):
        run(f"docker cp {REMOTE_ROOT}/backend/tests/{t} {BACKEND}:/app/tests/{t}")

    # 3. 容器内 pytest（静态断言 + 后端模式偏好接口回归）
    print("\n--- 容器内 pytest ---")
    c, o, e = run(
        f"docker exec -w /app {BACKEND} python -m pytest "
        f"tests/test_ai_home_unify_v1_20260601.py tests/test_ai_home_mode_capsule_v1_20260531.py "
        f"-v --no-header 2>&1",
        timeout=600,
    )
    print(o)
    if e.strip():
        print("--STDERR--\n" + e)
    cli.close()
    sys.exit(0 if c == 0 else 1)


if __name__ == "__main__":
    main()
