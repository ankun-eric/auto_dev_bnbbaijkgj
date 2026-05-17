"""[BUG_FIX_TIMEZONE_GLOBAL_20260517] 验证脚本：抽查若干 API 返回的 datetime 字段是否都带 UTC 后缀"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

# 待抽查的接口（不依赖登录态的公开接口为主）
ENDPOINTS = [
    "/api/health",
    "/api/system/server-time",
    "/api/home/config",
    "/api/bottom-nav/list",
    "/api/themes",
    "/api/login-ui-config",
    "/api/app-settings/global",
    "/api/services/filter",
    "/api/products/list",
    "/api/stores/public",
]


def _get(url: str, timeout: int = 15) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "tz-verify/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return -1, str(e)


def _find_datetime_fields(obj, path="$"):
    """递归找出所有形如 ISO 8601 datetime 的字符串字段，返回 [(path, value)]"""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(_find_datetime_fields(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_find_datetime_fields(v, f"{path}[{i}]"))
    elif isinstance(obj, str):
        # 形如 "2026-05-17T..."
        if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", obj):
            out.append((path, obj))
    return out


def main() -> int:
    print(f"=== [TIMEZONE_GLOBAL] 验证开始 ===")
    total_bad = 0
    total_ok = 0
    total_calls = 0
    for ep in ENDPOINTS:
        url = BASE + ep
        code, body = _get(url)
        total_calls += 1
        if code != 200:
            print(f"[skip] {ep}: HTTP {code} {body[:80]}")
            continue
        try:
            data = json.loads(body)
        except Exception:
            print(f"[skip] {ep}: not JSON")
            continue
        dt_fields = _find_datetime_fields(data)
        if not dt_fields:
            print(f"[--  ] {ep}: 无 datetime 字段")
            continue
        bad = []
        for p, v in dt_fields:
            has_tz = bool(re.search(r"Z$|[+-]\d{2}:?\d{2}$", v))
            if has_tz:
                total_ok += 1
            else:
                bad.append((p, v))
                total_bad += 1
        if bad:
            print(f"[FAIL] {ep}: {len(bad)} 个字段无时区后缀")
            for p, v in bad[:3]:
                print(f"        {p} = {v!r}")
        else:
            print(f"[ OK ] {ep}: {len(dt_fields)} 个 datetime 字段全部带 UTC 后缀")
    print("=== 汇总 ===")
    print(f"calls={total_calls}  datetime_ok={total_ok}  datetime_bad={total_bad}")
    if total_bad > 0:
        print("[FAIL] 仍有字段无时区后缀，部署可能未生效或存在自定义 response")
        return 1
    if total_ok == 0:
        print("[WARN] 没抽到任何 datetime 字段，无法判断")
        return 2
    print("[PASS] 所有抽样字段全部带 UTC 后缀，时区根治生效")
    return 0


if __name__ == "__main__":
    sys.exit(main())
