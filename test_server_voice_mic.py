#!/usr/bin/env python3
"""
Non-UI automated tests for voice search / search-result page (server HTTPS).
Verifies APIs, page reachability, and bundled JS / HTML hints for microphone UI.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urljoin

import requests

BASE = "https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
API = f"{BASE}/api"
TIMEOUT = 30
MAX_CHUNK_BYTES = 800_000
MAX_CHUNKS = 12

# Initial HTML may be a Next.js shell; mic UI lives in client JS.
MIC_HTML_KEYWORDS = (
    "microphone",
    "recording",
    "voice",
    "asr",
    "getusermedia",
    "mediarecorder",
)
# Minified bundles usually keep these substrings:
JS_VOICE_MARKERS = (
    "getUserMedia",
    "MediaRecorder",
    "search/asr",
    "audio_file",
    "source=voice",
)


@dataclass
class CaseResult:
    name: str
    ok: bool
    detail: str = ""
    status_code: int | None = None


@dataclass
class Report:
    results: list[CaseResult] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "", status_code: int | None = None) -> None:
        self.results.append(CaseResult(name=name, ok=ok, detail=detail, status_code=status_code))

    def summary(self) -> tuple[int, int, int]:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.ok)
        failed = total - passed
        return total, passed, failed


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return None


def test_get_ok(
    report: Report,
    name: str,
    url: str,
    *,
    min_status: int = 200,
    max_status: int = 299,
    auth_headers: dict[str, str] | None = None,
) -> requests.Response | None:
    try:
        r = requests.get(url, timeout=TIMEOUT, headers=auth_headers or {})
        ok = min_status <= r.status_code <= max_status
        detail = f"status={r.status_code}, len={len(r.content)}"
        if not ok:
            detail += f" body_preview={r.text[:300]!r}"
        report.add(name, ok, detail, r.status_code)
        return r
    except requests.RequestException as e:
        report.add(name, False, f"request error: {e}", None)
        return None


def test_post_json(
    report: Report,
    name: str,
    url: str,
    payload: dict | None = None,
    *,
    min_status: int = 200,
    max_status: int = 299,
) -> requests.Response | None:
    try:
        r = requests.post(
            url,
            json=payload or {},
            timeout=TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
        ok = min_status <= r.status_code <= max_status
        detail = f"status={r.status_code}"
        j = _safe_json(r)
        if j is not None:
            detail += f", json_keys={list(j.keys()) if isinstance(j, dict) else type(j).__name__}"
        else:
            detail += f", body_preview={r.text[:200]!r}"
        if not ok:
            detail += f" full_preview={r.text[:400]!r}"
        report.add(name, ok, detail, r.status_code)
        return r
    except requests.RequestException as e:
        report.add(name, False, f"request error: {e}", None)
        return None


def check_search_api(report: Report) -> None:
    url = f"{API}/search?q={quote('感冒')}&type=all"
    r = test_get_ok(report, "GET /api/search?q=感冒&type=all", url)
    if r and r.status_code == 200:
        j = _safe_json(r)
        if isinstance(j, dict) and ("data" in j or "items" in j or "results" in j or "list" in j):
            pass
        elif isinstance(j, list):
            pass
        else:
            for res in report.results:
                if res.name == "GET /api/search?q=感冒&type=all":
                    res.detail += " [warn: unexpected JSON shape]"


def _extract_script_urls(html: str, page_url: str) -> list[str]:
    urls: list[str] = []
    for m in re.finditer(
        r'<script[^>]+src=["\']([^"\']+)["\']',
        html,
        flags=re.I,
    ):
        src = m.group(1).strip()
        if not src or src.startswith("data:"):
            continue
        urls.append(urljoin(page_url, src))

    def sort_key(u: str) -> tuple[int, str]:
        ul = u.lower()
        # Prefer route-related chunks first (smaller set, faster pass)
        if "search" in ul or "result" in ul:
            return (0, u)
        if "app/" in ul or "pages/" in ul:
            return (1, u)
        return (2, u)

    return sorted(set(urls), key=sort_key)


def check_search_result_voice_bundle(report: Report) -> None:
    """HTML is often SSR shell; confirm voice-related code exists in linked JS."""
    page_path = f"/search/result?q={quote('感冒')}"
    page_url = f"{BASE}{page_path}"
    name = "GET /search/result voice UI in bundles (HTML+JS)"
    try:
        r = requests.get(page_url, timeout=TIMEOUT)
        if r.status_code != 200:
            report.add(name, False, f"page status={r.status_code}", r.status_code)
            return
        html = r.text or ""
        lower = html.lower()
        html_hits = [k for k in MIC_HTML_KEYWORDS if k in lower]

        script_urls = _extract_script_urls(html, page_url)
        combined = lower
        fetched = 0
        total_bytes = 0
        chunk_errors: list[str] = []

        for u in script_urls:
            if not u.endswith(".js") and "/_next/" not in u:
                continue
            if total_bytes >= MAX_CHUNK_BYTES or fetched >= MAX_CHUNKS:
                break
            try:
                cr = requests.get(u, timeout=TIMEOUT)
                if cr.status_code != 200:
                    chunk_errors.append(f"{u.split('/')[-1]}:{cr.status_code}")
                    continue
                body = cr.text or ""
                combined += body
                total_bytes += len(body)
                fetched += 1
                # Early exit once voice pipeline is provably in fetched JS
                c = combined
                if ("getUserMedia" in c and "MediaRecorder" in c) and (
                    "search/asr" in c or "audio_file" in c or "source=voice" in c
                ):
                    break
            except requests.RequestException as e:
                chunk_errors.append(f"{u}: {e}")

        js_hits = [m for m in JS_VOICE_MARKERS if m in combined]
        # Strong signal: browser capture APIs used together with ASR route or upload
        has_voice = ("getUserMedia" in combined and "MediaRecorder" in combined) or (
            "getUserMedia" in combined and ("search/asr" in combined or "audio_file" in combined)
        )
        ok = bool(has_voice or (len(js_hits) >= 3))
        detail = (
            f"page_status=200, html_keyword_hits={html_hits or 'none'}, "
            f"js_markers_matched={js_hits}, scripts_fetched={fetched}, "
            f"bytes≈{total_bytes}"
        )
        if chunk_errors:
            detail += f", chunk_warn={chunk_errors[:5]}"
        if not ok:
            detail += (
                " [FAIL: no getUserMedia+MediaRecorder/asr pipeline markers in HTML+loaded JS; "
                "Next.js may have changed chunk split — verify manually in browser]"
            )
        report.add(name, ok, detail, r.status_code)
    except requests.RequestException as e:
        report.add(name, False, str(e), None)


def test_search_history(report: Report) -> None:
    """History usually requires auth: 200 = ok; 401 = route exists (acceptable for anon)."""
    name = "GET /api/search/history"
    try:
        r = requests.get(f"{API}/search/history", timeout=TIMEOUT)
        if r.status_code == 200:
            report.add(name, True, f"status=200, len={len(r.content)}", 200)
        elif r.status_code == 401:
            report.add(
                name,
                True,
                "status=401 (unauthenticated — endpoint reachable, auth required for data)",
                401,
            )
        else:
            report.add(
                name,
                False,
                f"unexpected status={r.status_code}, preview={r.text[:200]!r}",
                r.status_code,
            )
    except requests.RequestException as e:
        report.add(name, False, f"request error: {e}", None)


def main() -> int:
    report = Report()

    test_get_ok(report, "GET /api/health", f"{API}/health")

    check_search_api(report)
    test_get_ok(report, "GET /api/search/hot", f"{API}/search/hot")
    test_get_ok(report, "GET /api/search/suggest?q=头", f"{API}/search/suggest?q={quote('头')}")

    test_post_json(
        report,
        "POST /api/search/asr/token",
        f"{API}/search/asr/token",
        {},
        min_status=200,
        max_status=299,
    )

    test_search_history(report)

    test_get_ok(report, "GET / (home)", f"{BASE}/")
    test_get_ok(report, "GET /search", f"{BASE}/search")
    test_get_ok(report, "GET /search/result?q=感冒", f"{BASE}/search/result?q={quote('感冒')}")

    check_search_result_voice_bundle(report)

    total, passed, failed = report.summary()

    print("=" * 60)
    print("VOICE / MIC SEARCH — SERVER NON-UI TEST REPORT")
    print("=" * 60)
    print(f"Base URL: {BASE}")
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}")
    print("-" * 60)
    for r in report.results:
        status = "PASS" if r.ok else "FAIL"
        sc = r.status_code if r.status_code is not None else "-"
        print(f"[{status}] ({sc}) {r.name}")
        print(f"        {r.detail}")
    print("=" * 60)

    out = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "cases": [
            {
                "name": x.name,
                "ok": x.ok,
                "status_code": x.status_code,
                "detail": x.detail,
            }
            for x in report.results
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
