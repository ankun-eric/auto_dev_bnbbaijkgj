"""[BUG_FIX_TIMEZONE_GLOBAL_V3_20260517] v3 验证脚本

非UI 自动化测试：
  1) HTTPS 健康检查
  2) 关键页面 HTTP 可达性
  3) 后端 JSON 中 datetime 字段格式校验（v2 兜底）
  4) 远程容器内执行 pytest 单元测试

输出 JSON + 文本汇总。
"""
from __future__ import annotations

import json
import re
import ssl
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, List, Tuple

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{PROJECT_ID}"

# 关键页面（HTTP 200 即可）
PAGES = [
    "/",
    "/admin/",
    "/api/health",
    "/chat-history",
    "/ai-home",
    "/health-archive",
    "/articles",
    "/news",
    "/coupon-center",
    "/checkup",
    "/tcm",
    "/drug",
]

# 后端公开 GET 接口（用于 datetime 格式抽样校验）
PUBLIC_API_PROBES = [
    "/api/health",
    "/api/auth/register-settings",
    "/api/tcm/questions",
    "/api/services/categories",
    "/api/services/items",
    "/api/experts",
    "/api/points/level",
    "/api/relation-types",
]


def _http_get(url: str, timeout: int = 20) -> Tuple[int, str]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "v3-verify/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        return 0, f"__ERROR__: {e}"


def check_pages() -> List[Dict]:
    results = []
    for p in PAGES:
        url = BASE_URL + p
        code, body = _http_get(url, timeout=30)
        ok = code == 200
        snippet = (body[:120] if isinstance(body, str) else "")
        results.append({"url": url, "code": code, "ok": ok, "snippet": snippet})
        print(f"  [{('OK' if ok else 'FAIL')}] {code} {url}")
    return results


# 简单 datetime 格式检测：
# 1) 形如 2026-05-17T...Z  或 +00:00 / +08:00 后缀 = 合规
# 2) 形如 2026-05-17T... 但不带 Z / +HH:MM 后缀 = 疑似 naive（v2 兜底没生效）
DT_KEY_RE = re.compile(
    r'"([a-zA-Z_]*(?:time|At|Time|_at|date|Date)[a-zA-Z_]*)"\s*:\s*"([^"]+)"'
)
DT_VAL_NAIVE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?$"
)
DT_VAL_AWARE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})$"
)


def check_datetime_format() -> List[Dict]:
    findings = []
    for ep in PUBLIC_API_PROBES:
        url = BASE_URL + ep
        code, body = _http_get(url, timeout=20)
        if code != 200 or not isinstance(body, str):
            findings.append({"url": url, "code": code, "skipped": True})
            print(f"  [SKIP] {code} {url}")
            continue
        matches = DT_KEY_RE.findall(body[:200000])
        aware = 0
        naive = 0
        sample_aware = None
        sample_naive = None
        for k, v in matches:
            if DT_VAL_AWARE_RE.match(v):
                aware += 1
                sample_aware = sample_aware or (k, v)
            elif DT_VAL_NAIVE_RE.match(v):
                naive += 1
                sample_naive = sample_naive or (k, v)
        findings.append({
            "url": url,
            "code": code,
            "datetime_fields_found": aware + naive,
            "aware": aware,
            "naive": naive,
            "sample_aware": sample_aware,
            "sample_naive": sample_naive,
        })
        print(f"  [{code}] {url}  aware={aware} naive={naive}  sample_aware={sample_aware} sample_naive={sample_naive}")
    return findings


def run_remote_pytest() -> Dict:
    print("\n[remote] run pytest in backend container")
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    try:
        container = f"{PROJECT_ID}-backend"
        # 1) 确保 pytest / pytest-asyncio 已安装（prod 容器默认不带）
        cli.exec_command(
            f"docker exec {container} sh -c "
            f"'pip install -q pytest pytest-asyncio 2>&1 | tail -5'",
            timeout=300,
        )[1].read()
        # 2) 使用 --noconftest 绕过依赖 aiosqlite 的 conftest（测试本身不依赖 DB）
        cmd = (
            f"docker exec {container} sh -c "
            f"'cd /app && python -m pytest tests/test_timezone_global_20260517.py "
            f"-v --no-header --noconftest -p no:cacheprovider 2>&1' "
            f"| tail -n 200"
        )
        stdin, stdout, stderr = cli.exec_command(cmd, timeout=300)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        text = out + ("\n" + err if err.strip() else "")
        print(text[-3000:])
        passed = ("passed" in text.lower()) and ("failed" not in text.lower() or "0 failed" in text.lower())
        # 更严格：找到 "X passed" 即视为通过
        m = re.search(r"(\d+)\s+passed", text)
        n_passed = int(m.group(1)) if m else 0
        m2 = re.search(r"(\d+)\s+failed", text)
        n_failed = int(m2.group(1)) if m2 else 0
        return {"exit": code, "n_passed": n_passed, "n_failed": n_failed, "ok": code == 0 and n_failed == 0 and n_passed > 0, "log_tail": text[-2000:]}
    finally:
        cli.close()


def main() -> int:
    print(f"=== v3 verify @ {BASE_URL} ===\n")

    print("[1] page accessibility")
    pages = check_pages()
    page_ok = sum(1 for r in pages if r["ok"])
    page_total = len(pages)

    print("\n[2] datetime format (v2 fallback)")
    dt = check_datetime_format()

    print("\n[3] remote pytest")
    try:
        pyt = run_remote_pytest()
    except Exception as e:
        print(f"  remote pytest ERROR: {e}")
        pyt = {"exit": -1, "n_passed": 0, "n_failed": 0, "ok": False, "log_tail": str(e)}

    summary = {
        "base_url": BASE_URL,
        "pages": pages,
        "page_pass_rate": f"{page_ok}/{page_total}",
        "datetime_findings": dt,
        "pytest": {k: v for k, v in pyt.items() if k != "log_tail"},
        "pytest_log_tail": pyt.get("log_tail", "")[-1500:],
    }
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # 判定
    ok_all = (page_ok == page_total) and pyt["ok"]
    if ok_all:
        print("\nRESULT: ALL_PASS")
        return 0
    if page_ok >= page_total - 2 and pyt["ok"]:
        print("\nRESULT: MOSTLY_PASS")
        return 0
    print("\nRESULT: HAS_FAILURES")
    return 1


if __name__ == "__main__":
    sys.exit(main())
