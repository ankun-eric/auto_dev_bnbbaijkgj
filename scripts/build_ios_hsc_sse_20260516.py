"""健康自查 SSE iOS GitHub Actions 远程构建脚本（2026-05-16）。

通过 GitHub Actions 的 macos-latest Runner 远程构建 iOS 包，并发布到 GitHub Release。
不依赖本地 macOS / Xcode 环境，Windows 上也可正常执行。

变更覆盖：
    - flutter_app/lib/screens/ai/chat_screen.dart
    - flutter_app/lib/widgets/health_self_check_drawer.dart
    - flutter_app/lib/widgets/health_self_check_card.dart

流程：
    1. 生成唯一版本标签 ios-v<YYYYMMDD>-<HHMMSS>-<4hex>
    2. gh workflow run ios-build.yml -f version=<tag>（带 3 次重试，10/20/40s 间隔）
    3. 通过 gh run list 定位 run id
    4. 每 30s 轮询 gh run view 直到完成或超时 30 分钟
    5. 失败则 gh run view --log-failed，最多整体重试 2 次
    6. 成功后 gh release view 拿到 Release 页 URL 与 IPA 直链
    7. 输出 RESULT_JSON 供上层解析

用法：
    python scripts/build_ios_hsc_sse_20260516.py
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

REPO = "ankun-eric/auto_dev_bnbbaijkgj"
WORKFLOW = "ios-build.yml"
POLL_INTERVAL_SEC = 30
MAX_WAIT_SEC = 30 * 60
GH_MAX_RETRIES = 3
GH_RETRY_BACKOFF = [10, 20, 40]
BUILD_MAX_ATTEMPTS = 2  # 整体构建最多重试 2 次（即最多触发 2 次 workflow）


def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_gh(args: list[str], retries: int = GH_MAX_RETRIES, timeout: int = 120) -> subprocess.CompletedProcess:
    """带网络重试的 gh 命令执行（国内访问 GitHub 不稳定）。"""
    last_err = None
    for i in range(retries):
        try:
            res = subprocess.run(
                ["gh", *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            if res.returncode == 0:
                return res
            last_err = f"exit={res.returncode}\nstdout={res.stdout}\nstderr={res.stderr}"
            log(f"gh {' '.join(args)} failed (attempt {i+1}/{retries}): {last_err[:300]}")
        except Exception as e:
            last_err = repr(e)
            log(f"gh {' '.join(args)} exception (attempt {i+1}/{retries}): {last_err}")
        if i < retries - 1:
            wait = GH_RETRY_BACKOFF[min(i, len(GH_RETRY_BACKOFF) - 1)]
            log(f"retrying after {wait}s ...")
            time.sleep(wait)
    raise RuntimeError(f"gh command failed after {retries} retries: gh {' '.join(args)}\n{last_err}")


def generate_version() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = f"{random.randint(0, 0xFFFF):04x}"
    return f"ios-v{ts}-{suffix}"


def trigger_workflow(version: str) -> None:
    log(f"Triggering workflow: {WORKFLOW} version={version}")
    run_gh([
        "workflow", "run", WORKFLOW,
        "-R", REPO,
        "-f", f"version={version}",
    ])
    log("workflow_dispatch sent")


def find_run_id(since_ts: float) -> str | None:
    res = run_gh([
        "run", "list",
        "-R", REPO,
        "--workflow", WORKFLOW,
        "--limit", "10",
        "--json", "databaseId,displayTitle,name,createdAt,event,status,conclusion",
    ])
    runs = json.loads(res.stdout)
    for r in runs:
        if r.get("event") != "workflow_dispatch":
            continue
        try:
            created = datetime.strptime(r["createdAt"], "%Y-%m-%dT%H:%M:%SZ").timestamp()
        except Exception:
            created = 0
        # 容差：trigger 时间前后各放宽 60s
        if created + 5 >= since_ts - 60:
            return str(r["databaseId"])
    if runs:
        return str(runs[0]["databaseId"])
    return None


def get_run_status(run_id: str) -> tuple[str, str | None]:
    res = run_gh([
        "run", "view", run_id,
        "-R", REPO,
        "--json", "status,conclusion",
    ])
    data = json.loads(res.stdout)
    return data.get("status", ""), data.get("conclusion")


def wait_for_run(run_id: str) -> str:
    log(f"Waiting for run {run_id} (timeout {MAX_WAIT_SEC}s, poll every {POLL_INTERVAL_SEC}s)")
    start = time.time()
    while time.time() - start < MAX_WAIT_SEC:
        try:
            status, conclusion = get_run_status(run_id)
        except Exception as e:
            log(f"  poll error: {e!r} — keep polling")
            time.sleep(POLL_INTERVAL_SEC)
            continue
        elapsed = int(time.time() - start)
        log(f"  run {run_id}: status={status} conclusion={conclusion} elapsed={elapsed}s")
        if status == "completed":
            return conclusion or ""
        time.sleep(POLL_INTERVAL_SEC)
    raise TimeoutError(f"Run {run_id} did not complete within {MAX_WAIT_SEC}s")


def dump_failed_logs(run_id: str, tail_lines: int = 200) -> str:
    try:
        res = subprocess.run(
            ["gh", "run", "view", run_id, "-R", REPO, "--log-failed"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240,
        )
        out = (res.stdout or "") + (res.stderr or "")
        lines = out.splitlines()
        tail = "\n".join(lines[-tail_lines:])
        log(f"--- failed log tail ({tail_lines} lines) ---\n{tail}\n--- end ---")
        return tail
    except Exception as e:
        log(f"failed to fetch failed logs: {e}")
        return ""


def get_release(version: str) -> dict:
    res = run_gh([
        "release", "view", version,
        "-R", REPO,
        "--json", "url,assets,tagName,name",
    ])
    return json.loads(res.stdout)


def verify_url(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ios-build-checker"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return -1, repr(e)


def attempt_build(version: str) -> tuple[str, str, str]:
    """触发并等待一次构建。返回 (run_id, run_url, conclusion)。"""
    trigger_started = time.time()
    trigger_workflow(version)

    time.sleep(8)
    run_id = None
    for attempt in range(8):
        try:
            run_id = find_run_id(trigger_started)
        except Exception as e:
            log(f"find_run_id error: {e!r}")
            run_id = None
        if run_id:
            break
        log(f"run not found yet, retry {attempt+1}/8")
        time.sleep(5)
    if not run_id:
        raise RuntimeError("could not locate the dispatched run")

    run_url = f"https://github.com/{REPO}/actions/runs/{run_id}"
    log(f"Tracking run id: {run_id}")
    log(f"Run URL: {run_url}")

    conclusion = wait_for_run(run_id)
    return run_id, run_url, conclusion


def main() -> int:
    overall_start = time.time()

    last_version = None
    last_run_id = None
    last_run_url = None
    last_conclusion = None
    last_build_seconds = 0

    for build_attempt in range(1, BUILD_MAX_ATTEMPTS + 1):
        version = generate_version()
        last_version = version
        log("=" * 60)
        log(f"Build attempt {build_attempt}/{BUILD_MAX_ATTEMPTS} — version={version}")
        log("=" * 60)

        attempt_started = time.time()
        try:
            run_id, run_url, conclusion = attempt_build(version)
        except Exception as e:
            log(f"attempt_build failed: {e!r}")
            last_build_seconds = int(time.time() - attempt_started)
            last_conclusion = "infrastructure_error"
            continue

        last_run_id = run_id
        last_run_url = run_url
        last_conclusion = conclusion
        last_build_seconds = int(time.time() - attempt_started)
        log(f"Attempt {build_attempt} finished: conclusion={conclusion} in {last_build_seconds}s")

        if conclusion == "success":
            break

        dump_failed_logs(run_id)
        if build_attempt < BUILD_MAX_ATTEMPTS:
            log(f"Build attempt {build_attempt} failed, will retry with new version tag ...")
            time.sleep(15)

    if last_conclusion != "success":
        log("=" * 60)
        log("BUILD_FAILED (all attempts exhausted)")
        log(f"  version:    {last_version}")
        log(f"  run_id:     {last_run_id}")
        log(f"  run_url:    {last_run_url}")
        log(f"  conclusion: {last_conclusion}")
        log("=" * 60)
        out = {
            "ok": False,
            "version": last_version,
            "run_id": last_run_id,
            "run_url": last_run_url,
            "conclusion": last_conclusion,
            "build_seconds": last_build_seconds,
            "total_seconds": int(time.time() - overall_start),
        }
        print("RESULT_JSON=" + json.dumps(out, ensure_ascii=False))
        return 3

    try:
        rel = get_release(last_version)
    except Exception as e:
        log(f"Could not fetch release: {e}")
        return 4

    release_url = rel.get("url") or f"https://github.com/{REPO}/releases/tag/{last_version}"
    assets = rel.get("assets") or []
    ipa_url = None
    ipa_name = None
    for a in assets:
        name = a.get("name", "")
        if name.lower().endswith(".ipa"):
            ipa_url = a.get("url") or a.get("browserDownloadUrl") or a.get("apiUrl")
            ipa_name = name
            break
    if not ipa_url and assets:
        a = assets[0]
        ipa_url = a.get("url") or a.get("browserDownloadUrl")
        ipa_name = a.get("name")
    if not ipa_url:
        ipa_url = f"https://github.com/{REPO}/releases/download/{last_version}/bini_health_ios.ipa"
        ipa_name = "bini_health_ios.ipa"

    log(f"Release URL: {release_url}")
    log(f"IPA download URL: {ipa_url}")

    page_code, page_ctype = verify_url(release_url)
    log(f"Release page HTTP status: {page_code} ({page_ctype})")

    total = int(time.time() - overall_start)
    log("=" * 60)
    log("BUILD_SUCCESS")
    log(f"  version:        {last_version}")
    log(f"  run_id:         {last_run_id}")
    log(f"  run_url:        {last_run_url}")
    log(f"  release_url:    {release_url}")
    log(f"  ipa_name:       {ipa_name}")
    log(f"  ipa_download:   {ipa_url}")
    log(f"  release_http:   {page_code}")
    log(f"  build_seconds:  {last_build_seconds}")
    log(f"  total_seconds:  {total}")
    log("=" * 60)

    out = {
        "ok": True,
        "version": last_version,
        "run_id": last_run_id,
        "run_url": last_run_url,
        "release_url": release_url,
        "ipa_name": ipa_name,
        "ipa_download": ipa_url,
        "release_http": page_code,
        "build_seconds": last_build_seconds,
        "total_seconds": total,
        "conclusion": last_conclusion,
    }
    print("RESULT_JSON=" + json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
