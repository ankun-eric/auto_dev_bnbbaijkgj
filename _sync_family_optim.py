"""[PRD-FAMILY-MEMBER-OPTIM-FINAL 2026-05-31] 同步本次改动到服务器并触发 H5 重建。

仅同步本次新增/修改的文件，不动其他工程文件。
"""
import os
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"

# 本次改动的文件（相对项目根目录）
FILES = [
    "h5-web/src/components/ai-chat/ConsultTargetPicker.tsx",
    "h5-web/src/components/health-profile-v5/NewFamilyMemberModal.tsx",
    "h5-web/src/app/family-invite/page.tsx",
    "miniprogram/pages/chat/index.js",
    "miniprogram/pages/chat/index.wxml",
    "miniprogram/pages/chat/index.wxss",
    "miniprogram/pages/family-member-add/index.js",
    "miniprogram/pages/family-member-add/index.wxml",
    "miniprogram/pages/family-member-add/index.wxss",
    "miniprogram/pages/family-invite/index.wxml",
    "miniprogram/pages/family-invite/index.wxss",
    "flutter_app/lib/screens/ai/chat_screen.dart",
    "flutter_app/lib/screens/family/family_invite_screen.dart",
    "backend/tests/test_family_member_optim_final_20260531.py",
]


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = cli.open_sftp()
    for rel in FILES:
        local = rel.replace("/", os.sep)
        remote = f"{REMOTE_ROOT}/{rel}"
        # 确保远端目录存在
        remote_dir = remote.rsplit("/", 1)[0]
        try:
            stdin, stdout, stderr = cli.exec_command(f"mkdir -p {remote_dir}")
            stdout.channel.recv_exit_status()
        except Exception:
            pass
        try:
            sftp.put(local, remote)
            print(f"[OK] {rel}")
        except Exception as e:
            print(f"[FAIL] {rel}: {e}")
    sftp.close()
    cli.close()


if __name__ == "__main__":
    main()
