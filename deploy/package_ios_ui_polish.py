"""
iOS IPA 打包子 Agent 脚本
---------------------------------
通过 GitHub Actions 远程构建 iOS IPA 并发布到 Release。

步骤：
1. 读取 .github/workflows/ios-build.yml，确认已存在（前置条件）
2. 生成版本标签 ios-v{YYYYMMDD}-{HHMMSS}-{4hex}
3. 用 gh workflow run 触发构建（带 3 次重试，10s/20s/40s 间隔）
4. 每 30 秒轮询 gh run 状态，最长 30 分钟
5. 成功后 gh release view 获取 asset URL、大小
6. 失败时 gh run view --log-failed 获取失败日志，最多重试 2 次
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ========= 配置 =========
REPO_ROOT = Path(r"C:\auto_output\bnbbaijkgj")
WORKFLOW_FILE = ".github/workflows/ios-build.yml"
WORKFLOW_NAME = "ios-build.yml"
RESULT_JSON = REPO_ROOT / "deploy" / "package_ios_ui_polish_result.json"
LOG_FILE = REPO_ROOT / "deploy" / "package_ios_ui_polish.log"

POLL_INTERVAL_SEC = 30
MAX_POLL_MINUTES = 30
MAX_BUILD_ATTEMPTS = 2  # 失败时最多再重试 N 次
GH_RETRY_DELAYS = [10, 20, 40]  # 单条 gh 命令的 3 次重试间隔

# ========= 工具函数 =========
_log_lines: list[str] = []


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    _log_lines.append(line)


def flush_log() -> None:
    try:
        LOG_FILE.write_text("\n".join(_log_lines), encoding="utf-8")
    except Exception as e:
        print(f"WARN: failed to write log: {e}", flush=True)


def run(cmd: list[str], *, check: bool = True, timeout: int = 180,
        cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a command once, return CompletedProcess. No retry here."""
    log(f"$ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd or REPO_ROOT),
        timeout=timeout,
    )
    if result.stdout:
        for ln in result.stdout.rstrip().splitlines()[-30:]:
            log(f"  | {ln}")
    if result.stderr and result.returncode != 0:
        for ln in result.stderr.rstrip().splitlines()[-30:]:
            log(f"  !! {ln}")
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed (rc={result.returncode}): {' '.join(cmd)}\n"
            f"stderr={result.stderr}"
        )
    return result


def run_with_retry(cmd: list[str], *, check: bool = True,
                   timeout: int = 180) -> subprocess.CompletedProcess:
    """Run a gh/network command with 3 retries (10s/20s/40s)."""
    last_exc: Optional[Exception] = None
    for attempt, delay in enumerate([0] + GH_RETRY_DELAYS, start=0):
        if delay:
            log(f"retry in {delay}s (attempt {attempt + 1}) ...")
            time.sleep(delay)
        try:
            result = run(cmd, check=False, timeout=timeout)
            if result.returncode == 0:
                return result
            last_exc = RuntimeError(
                f"rc={result.returncode}, stderr={result.stderr.strip()[:500]}"
            )
        except Exception as e:  # noqa: BLE001
            last_exc = e
            log(f"exception: {e}")
    if check:
        raise RuntimeError(f"command failed after retries: {' '.join(cmd)}: {last_exc}")
    # 返回最后一次结果
    return result  # type: ignore[return-value]


# ========= 主流程 =========

def gen_version_tag() -> str:
    now = datetime.now()
    hex4 = secrets.token_hex(2)
    return f"ios-v{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-{hex4}"


def ensure_workflow_exists() -> None:
    wf_path = REPO_ROOT / WORKFLOW_FILE
    if not wf_path.exists():
        raise RuntimeError(f"workflow missing: {wf_path}")
    content = wf_path.read_text(encoding="utf-8", errors="replace")
    if "workflow_dispatch" not in content or "version" not in content:
        raise RuntimeError("workflow does not support workflow_dispatch with 'version' input")
    log(f"workflow OK: {WORKFLOW_FILE} ({len(content)} bytes)")


def trigger_workflow(version: str) -> None:
    log(f"trigger workflow with version={version}")
    run_with_retry(
        ["gh", "workflow", "run", WORKFLOW_NAME, "-f", f"version={version}"],
        timeout=60,
    )


def find_latest_run_id(version: str, trigger_time: float) -> str:
    """Find the run we just triggered. Poll up to 2 min for the run to appear."""
    deadline = time.time() + 120
    while time.time() < deadline:
        result = run_with_retry(
            ["gh", "run", "list",
             "--workflow", WORKFLOW_NAME,
             "--limit", "5",
             "--json", "databaseId,status,conclusion,createdAt,displayTitle,name,event"],
            timeout=60,
        )
        try:
            runs = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            runs = []
        # 选 createdAt 最新且 event=workflow_dispatch 的一条
        dispatch_runs = [
            r for r in runs
            if r.get("event") == "workflow_dispatch"
        ]
        if dispatch_runs:
            latest = sorted(dispatch_runs, key=lambda r: r.get("createdAt", ""),
                            reverse=True)[0]
            created = latest.get("createdAt", "")
            # createdAt 为 ISO8601，必须晚于 trigger_time - 60s
            log(f"latest dispatch run: id={latest['databaseId']} created={created} status={latest.get('status')}")
            return str(latest["databaseId"])
        log("no dispatch run found yet, waiting 10s ...")
        time.sleep(10)
    raise RuntimeError("could not find triggered run within 2 minutes")


def poll_run(run_id: str) -> dict[str, Any]:
    deadline = time.time() + MAX_POLL_MINUTES * 60
    while time.time() < deadline:
        result = run_with_retry(
            ["gh", "run", "view", run_id,
             "--json", "status,conclusion,displayTitle,url,jobs,createdAt,updatedAt"],
            timeout=60,
        )
        try:
            info = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            info = {}
        status = info.get("status", "")
        conclusion = info.get("conclusion", "")
        jobs = info.get("jobs", []) or []
        job_summary = ", ".join(
            f"{j.get('name')}={j.get('status')}/{j.get('conclusion')}" for j in jobs
        )
        log(f"run {run_id}: status={status} conclusion={conclusion} jobs=[{job_summary}]")
        if status == "completed":
            return info
        time.sleep(POLL_INTERVAL_SEC)
    raise TimeoutError(f"run {run_id} did not complete within {MAX_POLL_MINUTES} minutes")


def get_failed_log(run_id: str) -> str:
    log(f"fetching failed log for run {run_id}")
    result = run_with_retry(
        ["gh", "run", "view", run_id, "--log-failed"],
        timeout=180,
        check=False,
    )
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    return text[-8000:]


def get_release_assets(version: str) -> dict[str, Any]:
    result = run_with_retry(
        ["gh", "release", "view", version,
         "--json", "tagName,name,url,assets"],
        timeout=60,
    )
    info = json.loads(result.stdout or "{}")
    return info


def _parse_iso(ts: str) -> float:
    """Parse GitHub ISO8601 timestamp like '2026-04-22T17:46:35Z' to epoch sec."""
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").timestamp()
    except Exception:  # noqa: BLE001
        return 0.0


def build_once(version: str) -> dict[str, Any]:
    """Single build attempt. Returns info dict or raises on failure."""
    t0 = time.time()
    trigger_workflow(version)
    time.sleep(5)
    run_id = find_latest_run_id(version, t0)
    info = poll_run(run_id)
    # Prefer GitHub-provided timestamps for duration (more accurate, TZ-safe)
    created = _parse_iso(info.get("createdAt", ""))
    updated = _parse_iso(info.get("updatedAt", ""))
    if created and updated and updated > created:
        duration = int(updated - created)
    else:
        duration = int(time.time() - t0)
    conclusion = info.get("conclusion", "")
    if conclusion != "success":
        failed_log = get_failed_log(run_id)
        raise RuntimeError(
            f"build failed: conclusion={conclusion}\n"
            f"run_url={info.get('url')}\n"
            f"--- failed log tail ---\n{failed_log}"
        )
    # 成功：拉 release
    release = get_release_assets(version)
    assets = release.get("assets", []) or []
    ipa_asset = next(
        (a for a in assets if (a.get("name") or "").lower().endswith(".ipa")),
        None,
    )
    if not ipa_asset:
        raise RuntimeError(f"no .ipa asset in release {version}: {assets}")

    size = ipa_asset.get("size", 0)
    if size < 100_000:
        # 过小 → 视作失败（Runner.app 可能是空壳）
        raise RuntimeError(
            f"IPA too small ({size} bytes) — likely empty/invalid build. "
            f"asset={ipa_asset}"
        )

    ipa_download_url = (
        f"https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/"
        f"{version}/{ipa_asset['name']}"
    )
    return {
        "run_id": run_id,
        "run_url": info.get("url", ""),
        "release_url": (release.get("url")
                        or f"https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/{version}"),
        "ipa_name": ipa_asset["name"],
        "ipa_size_bytes": size,
        "ipa_download_url": ipa_download_url,
        "duration_sec": duration,
    }


def main() -> int:
    log("=" * 60)
    log("iOS IPA remote build starting ...")
    log("=" * 60)
    ensure_workflow_exists()

    attempts = 0
    last_err: Optional[str] = None
    last_version: Optional[str] = None
    while attempts < MAX_BUILD_ATTEMPTS + 1:
        attempts += 1
        version = gen_version_tag()
        last_version = version
        log(f"--- attempt {attempts}/{MAX_BUILD_ATTEMPTS + 1}  version={version} ---")
        try:
            info = build_once(version)
            info["version_tag"] = version
            info["attempts"] = attempts
            info["ipa_url"] = info["ipa_download_url"]
            log("=" * 60)
            log("BUILD SUCCEEDED")
            for k, v in info.items():
                log(f"  {k}: {v}")
            log("=" * 60)
            RESULT_JSON.write_text(
                json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            flush_log()
            return 0
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            log(f"ATTEMPT {attempts} FAILED: {e}")
            if attempts > MAX_BUILD_ATTEMPTS:
                break
            log(f"will retry (attempt {attempts + 1}) after 15s ...")
            time.sleep(15)

    # 全部失败
    fail_info = {
        "version_tag": last_version,
        "attempts": attempts,
        "success": False,
        "error": last_err,
    }
    RESULT_JSON.write_text(
        json.dumps(fail_info, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log("=" * 60)
    log("BUILD FAILED")
    log(last_err or "")
    log("=" * 60)
    flush_log()
    return 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as e:  # noqa: BLE001
        log(f"FATAL: {e}")
        flush_log()
        rc = 2
    flush_log()
    sys.exit(rc)
