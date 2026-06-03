"""[PRD-MODE-CAPSULE-V1 2026-05-31] 上传改动文件并重建 H5 容器 + 运行后端测试"""
import sys
import posixpath
import _ssh_helper as sh

REMOTE_ROOT = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_ROOT = r"C:\auto_output\bnbbaijkgj"

# (local_rel, remote_rel)
FILES = [
    (r"h5-web\src\app\(ai-chat)\ai-home\page.tsx", "h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    (r"miniprogram\pages\ai\index.wxml", "miniprogram/pages/ai/index.wxml"),
    (r"miniprogram\pages\ai\index.js", "miniprogram/pages/ai/index.js"),
    (r"miniprogram\pages\ai\index.wxss", "miniprogram/pages/ai/index.wxss"),
    (r"backend\tests\test_ai_home_mode_capsule_v1_20260531.py", "backend/tests/test_ai_home_mode_capsule_v1_20260531.py"),
]


def ensure_remote_dir(remote_path):
    d = posixpath.dirname(remote_path)
    sh.run(f"mkdir -p '{d}'")


def upload():
    for lrel, rrel in FILES:
        lpath = f"{LOCAL_ROOT}\\{lrel}"
        rpath = f"{REMOTE_ROOT}/{rrel}"
        ensure_remote_dir(rpath)
        sh.put_file(lpath, rpath)
        print(f"uploaded: {rrel}")


if __name__ == "__main__":
    upload()
    print("ALL UPLOADED")
