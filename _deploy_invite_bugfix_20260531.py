"""[PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31 修复版] 部署脚本
上传本次修改的 h5-web + miniprogram + flutter_app + backend tests 文件
然后在服务器重建 h5-web 和 backend 容器（小程序文件无需重建容器，APK 由 GH Actions 打）
"""
import os
from _ssh_helper import get_client, put_file, run

REMOTE_ROOT = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

FILES = [
    # H5 修改
    "h5-web/src/app/family-invite/page.tsx",
    "h5-web/src/components/ai-chat/ConsultTargetPicker.tsx",
    "h5-web/src/components/health-profile-v5/NewFamilyMemberModal.tsx",
    # 小程序
    "miniprogram/pages/family-invite/index.js",
    "miniprogram/pages/family-invite/index.wxml",
    "miniprogram/pages/chat/index.js",
    # Flutter
    "flutter_app/lib/screens/ai/chat_screen.dart",
    # 后端测试
    "backend/tests/test_family_invite_bugfix_20260531.py",
]


def sftp_mkdir_p(sftp, remote_dir):
    parts = remote_dir.replace("\\", "/").strip("/").split("/")
    cur = ""
    for p in parts:
        cur = cur + "/" + p
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            try:
                sftp.mkdir(cur)
            except Exception:
                pass


def upload_all():
    client = get_client()
    try:
        sftp = client.open_sftp()
        for rel in FILES:
            local = os.path.join(os.path.dirname(__file__), rel.replace("/", os.sep))
            remote = f"{REMOTE_ROOT}/{rel}"
            remote_dir = remote.rsplit("/", 1)[0]
            sftp_mkdir_p(sftp, remote_dir)
            print(f"upload: {local} -> {remote}")
            sftp.put(local, remote)
        sftp.close()
    finally:
        client.close()


def rebuild_h5_and_backend():
    """重建 h5 和 backend 容器。"""
    cmds = [
        # 重建 h5-web（源码改 → 必须重新 build image）
        f"cd {REMOTE_ROOT} && docker compose build h5-web 2>&1 | tail -50",
        f"cd {REMOTE_ROOT} && docker compose up -d h5-web 2>&1 | tail -20",
        # backend 只改了 tests，不需要重建镜像，但可以重启使其重新加载（虽然 tests 不影响运行时）
        # 不重启 backend 以保留 mysql 数据连接
        "docker ps --filter name=6b099ed3 --format '{{.Names}}\t{{.Status}}'",
    ]
    for c in cmds:
        print(f"\n>>> {c}")
        rc, out, err = run(c, timeout=900)
        print(out)
        if err:
            print("STDERR:", err[:500])
        print(f"rc={rc}")


if __name__ == "__main__":
    print("=== 上传文件 ===")
    upload_all()
    print("\n=== 重建 H5 容器 ===")
    rebuild_h5_and_backend()
    print("\n部署完成。")
