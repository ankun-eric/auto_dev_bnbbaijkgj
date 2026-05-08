# -*- coding: utf-8 -*-
"""[BUG-410] 续作：上一次主脚本因 gh JSON 字段写错而误判超时，但 GitHub Actions 实际已成功；
本脚本直接复用已经构建好的 release（version=android-bug410-v20260508-120029-6770），
完成 download -> sftp upload -> HEAD verify。"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _build_apk_bug410 import (
    log, run, download_apk, sftp_upload, verify_download,
    make_remote_filename, get_run_url, BASE_URL,
)
import tempfile

VERSION = "android-bug410-v20260508-120029-6770"
RUN_ID = "25535917767"


def main():
    started = time.time()
    log("=" * 60)
    log(f"[bug410-resume] reusing existing release version={VERSION} run={RUN_ID}")
    run_url = get_run_url(RUN_ID)
    log(f"[bug410-resume] run url={run_url}")

    tmp_dir = tempfile.mkdtemp(prefix="apk_bug410_")
    src_apk, _ = download_apk(VERSION, tmp_dir)
    apk_size = os.path.getsize(src_apk)
    log(f"[bug410-resume] downloaded {src_apk} size={apk_size}")

    remote_name = make_remote_filename()
    log(f"[bug410-resume] uploading as {remote_name}")
    sftp_upload(src_apk, remote_name)

    download_url = f"{BASE_URL}/apk/{remote_name}"
    code, length = verify_download(download_url)
    if code != 200:
        log(f"[bug410-resume] FAILED HEAD code={code}")
        sys.exit(3)

    elapsed = int(time.time() - started)
    log("=" * 60)
    log("[bug410-resume] SUCCESS")
    log(f"  APK_VERSION_TAG = {VERSION}")
    log(f"  APK_FILENAME    = {remote_name}")
    log(f"  APK_SIZE        = {apk_size}")
    log(f"  APK_HTTP_STATUS = {code}")
    log(f"  APK_DOWNLOAD_URL= {download_url}")
    log(f"  GH_RUN_URL      = {run_url}")
    log(f"  RESUME_ELAPSED  = {elapsed}s")
    print("=" * 60)
    print(f"APK_VERSION_TAG={VERSION}")
    print(f"APK_FILENAME={remote_name}")
    print(f"APK_SIZE={apk_size}")
    print(f"APK_HTTP_STATUS={code}")
    print(f"APK_DOWNLOAD_URL={download_url}")
    print(f"GH_RUN_URL={run_url}")


if __name__ == "__main__":
    main()
