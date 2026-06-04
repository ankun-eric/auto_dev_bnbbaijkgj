"""[BUGFIX-FAMILY-DUPLICATE-BIND-V1] 降级方案：SFTP 上传本次后端修复文件到服务器。

服务器无法连接 GitHub（443 超时），按 remote-deploy-and-test 降级方案，
直接将本次修改的 3 个后端文件精确上传到服务器项目目录。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _sshlib import get_client, DEPLOY_ID

LOCAL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REMOTE_ROOT = f"/home/ubuntu/{DEPLOY_ID}"

FILES = [
    "backend/app/services/family_bind_dedup_service.py",
    "backend/app/api/family_management.py",
    "backend/app/api/reverse_guardian.py",
]


def main():
    c = get_client()
    try:
        sftp = c.open_sftp()
        for rel in FILES:
            local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
            remote = f"{REMOTE_ROOT}/{rel}"
            size = os.path.getsize(local)
            sftp.put(local, remote)
            # 验证大小
            rstat = sftp.stat(remote)
            print(f"UPLOADED {rel}  local={size}  remote={rstat.st_size}  {'OK' if rstat.st_size == size else 'SIZE-MISMATCH'}")
        sftp.close()
    finally:
        c.close()


if __name__ == "__main__":
    main()
