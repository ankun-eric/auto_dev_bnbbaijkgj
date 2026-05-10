#!/usr/bin/env python3
"""
PRD-442 Android APK 子 Agent B - 补救/最终化脚本

由于上一次构建+下载已成功，但 SFTP 上传被截断（远端 29MB vs 本地 84MB），
本脚本直接复用已下载的 APK，重新上传并完成 HTTP 验证。

策略：
- 复用 _prd442_android_dl/bini_health_android-prd442-v20260510110750-7248.apk
- 生成新文件名 app_prd442_<ts>_<hex>.apk
- 用 paramiko SFTP 直接上传到 /home/ubuntu/{DEPLOY_ID}/static/apk/
  （host 路径，nginx alias /data/static/apk/ 实际就是该目录的容器内挂载点）
- 上传时分块写入 + 校验大小，失败则重试
- urllib HTTP 验证返回 200 + 字节数
"""
from __future__ import annotations

import json
import random
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import paramiko

PROJECT_ROOT = Path(r"C:\auto_output\bnbbaijkgj")
LOG_PATH = PROJECT_ROOT / "_pack_prd442_android.log"
DL_DIR = PROJECT_ROOT / "_prd442_android_dl"

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_PORT = 22
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
REMOTE_APK_DIR = f"/home/ubuntu/{DEPLOY_ID}/static/apk"

VERSION_TAG = "android-prd442-v20260510110750-7248"
RUN_ID = "25618360520"
RELEASE_URL = f"https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/{VERSION_TAG}"


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def pick_local_apk() -> Path:
    candidates = sorted(DL_DIR.glob("bini_health_android-prd442-*.apk"))
    if not candidates:
        candidates = sorted(DL_DIR.glob("*.apk"))
    if not candidates:
        raise RuntimeError(f"找不到本地 APK 于 {DL_DIR}")
    # 选最大的（避免选到之前重命名的部分）
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    p = candidates[0]
    _log(f"使用本地 APK: {p} ({p.stat().st_size} bytes)")
    return p


def gen_remote_filename() -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    h = "".join(random.choice("0123456789abcdef") for _ in range(4))
    return f"app_prd442_{ts}_{h}.apk"


def sftp_upload(local_path: Path, remote_filename: str, max_attempts: int = 3) -> int:
    """SFTP 上传到 REMOTE_APK_DIR/remote_filename，返回远端字节数。
    失败时重试，校验远端大小必须 == 本地大小。"""
    local_size = local_path.stat().st_size
    final_remote = f"{REMOTE_APK_DIR}/{remote_filename}"

    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        _log(f"[SFTP attempt {attempt}/{max_attempts}] 上传 {local_path.name} -> {SSH_HOST}:{final_remote}")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            # 单独设置较大的 banner_timeout 与 keepalive
            client.connect(
                SSH_HOST, SSH_PORT, SSH_USER, SSH_PASS,
                timeout=60, banner_timeout=60, auth_timeout=60,
            )
            transport = client.get_transport()
            if transport is not None:
                transport.set_keepalive(15)
                # 加大窗口可帮助大文件
                try:
                    transport.window_size = 2 * 1024 * 1024
                    transport.packetizer.REKEY_BYTES = pow(2, 40)
                    transport.packetizer.REKEY_PACKETS = pow(2, 40)
                except Exception:
                    pass

            # 确保目录存在
            stdin, stdout, stderr = client.exec_command(
                f"mkdir -p {REMOTE_APK_DIR} && ls -ld {REMOTE_APK_DIR}",
                timeout=30,
            )
            out = stdout.read().decode(errors="replace").strip()
            if out:
                _log(f"  | {out}")

            sftp = client.open_sftp()
            try:
                # 流式分块上传，附带进度
                last_pct_logged = -10
                bytes_done = 0

                def cb(transferred: int, total: int) -> None:
                    nonlocal last_pct_logged, bytes_done
                    bytes_done = transferred
                    pct = int(transferred * 100 / max(total, 1))
                    if pct >= last_pct_logged + 20:
                        _log(f"  ... {pct}% ({transferred}/{total})")
                        last_pct_logged = pct

                t0 = time.time()
                sftp.put(str(local_path), final_remote, callback=cb, confirm=True)
                elapsed = time.time() - t0
                st = sftp.stat(final_remote)
                _log(f"  上传完成 in {elapsed:.1f}s, 远端大小 = {st.st_size} bytes (本地 {local_size})")
                if st.st_size != local_size:
                    raise RuntimeError(
                        f"上传后大小不匹配: remote={st.st_size}, local={local_size}"
                    )
                # 强制权限
                try:
                    sftp.chmod(final_remote, 0o644)
                except Exception:
                    pass
                return st.st_size
            finally:
                sftp.close()
        except Exception as e:
            last_err = e
            _log(f"  SFTP 失败 (attempt {attempt}): {e}")
            # 失败后清理远端残留
            try:
                stdin, stdout, stderr = client.exec_command(
                    f"rm -f {final_remote}", timeout=20
                )
                stdout.read()
            except Exception:
                pass
        finally:
            try:
                client.close()
            except Exception:
                pass

        if attempt < max_attempts:
            wait = 10 * attempt
            _log(f"  等 {wait}s 后重试 SFTP ...")
            time.sleep(wait)

    assert last_err is not None
    raise last_err


def verify_http(url: str, expect_size: int, max_attempts: int = 4) -> tuple[int, int]:
    _log(f"HTTP GET 验证: {url}")
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=120) as resp:
                code = resp.getcode()
                clen_hdr = resp.headers.get("Content-Length")
                size = int(clen_hdr) if clen_hdr else -1
                # 读 16 KB 确认实际可读
                _ = resp.read(16 * 1024)
                _log(f"  HTTP {code}, Content-Length={size} bytes (本地 {expect_size})")
                if code == 200 and size == expect_size:
                    return code, size
                if code == 200 and size > 0:
                    _log(f"  尺寸不一致，等几秒重试")
                if code != 200:
                    _log(f"  非 200，等几秒重试")
        except Exception as e:
            last_err = e
            _log(f"  验证失败 (attempt {attempt}/{max_attempts}): {e}")
        time.sleep(5 * attempt)
    if last_err is not None:
        raise last_err
    raise RuntimeError("HTTP 验证未达预期")


def main() -> int:
    summary: dict = {
        "version_tag": VERSION_TAG,
        "run_id": RUN_ID,
        "release_url": RELEASE_URL,
        "apk_filename": None,
        "download_url": None,
        "http_status": None,
        "byte_size": None,
        "error": None,
    }
    try:
        _log("=" * 70)
        _log("PRD-442 Android 子 Agent B - 最终化（重新上传 + HTTP 验证）")
        _log("=" * 70)

        local_apk = pick_local_apk()
        local_size = local_apk.stat().st_size

        remote_filename = gen_remote_filename()
        summary["apk_filename"] = remote_filename
        _log(f"目标远端文件名: {remote_filename}")

        remote_size = sftp_upload(local_apk, remote_filename, max_attempts=3)

        download_url = f"{BASE_URL}/apk/{remote_filename}"
        summary["download_url"] = download_url

        time.sleep(3)
        code, size = verify_http(download_url, expect_size=local_size, max_attempts=4)
        summary["http_status"] = code
        summary["byte_size"] = size

        if code != 200:
            raise RuntimeError(f"HTTP 验证失败: {code}")
        if size != local_size:
            _log(f"WARN: HTTP Content-Length 与本地不一致 (server={size}, local={local_size})")

        _log("=" * 70)
        _log("最终结果:")
        for k, v in summary.items():
            _log(f"  {k}: {v}")
        _log("=" * 70)
        _log("SUMMARY_JSON: " + json.dumps(summary, ensure_ascii=False))
        return 0
    except Exception as e:
        summary["error"] = str(e)
        _log(f"ERROR: {e}")
        _log("SUMMARY_JSON: " + json.dumps(summary, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
