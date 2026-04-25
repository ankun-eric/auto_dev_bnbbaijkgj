"""[PRD v1.0 §B1] 后端路由冲突全局扫描脚本

读取 FastAPI app 实例，找出 (path, method) 重复的接口，输出报告到 stdout
（如同时指定 --json 则输出到对应文件）。

用法：
    cd backend
    python -m app.scripts_run_scan_routes
    # 或：
    python backend/scripts/scan_route_conflicts.py [--json out.json]

退出码：
    0  无冲突
    1  存在冲突
    2  脚本错误
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any


def _ensure_app_importable() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    backend_root = os.path.abspath(os.path.join(here, ".."))
    project_root = os.path.abspath(os.path.join(backend_root, ".."))
    for p in (backend_root, project_root):
        if p not in sys.path:
            sys.path.insert(0, p)


def collect_conflicts(app) -> list[dict]:
    bucket: dict[tuple[str, str], list[str]] = {}
    for r in app.routes:
        path = getattr(r, "path", None)
        methods = getattr(r, "methods", None) or set()
        endpoint = getattr(r, "endpoint", None)
        if not path or endpoint is None:
            continue
        ep_name = f"{getattr(endpoint, '__module__', '?')}.{getattr(endpoint, '__name__', '?')}"
        for m in methods:
            bucket.setdefault((path, m.upper()), []).append(ep_name)
    return [
        {"path": p, "method": m, "endpoints": eps}
        for (p, m), eps in bucket.items()
        if len(eps) > 1
    ]


def main(argv: list[str]) -> int:
    _ensure_app_importable()
    out_json = None
    if "--json" in argv:
        i = argv.index("--json")
        if i + 1 < len(argv):
            out_json = argv[i + 1]
    try:
        from app.main import app  # type: ignore
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] 无法导入 app.main:app — {e}", file=sys.stderr)
        return 2
    conflicts = collect_conflicts(app)
    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump({"conflict_count": len(conflicts), "conflicts": conflicts}, f, ensure_ascii=False, indent=2)
        print(f"[OK] 报告已写入 {out_json}")
    if not conflicts:
        print("[OK] 路由冲突扫描通过：未发现 (path, method) 重复")
        return 0
    print(f"[FAIL] 发现 {len(conflicts)} 个路由冲突：")
    for c in conflicts:
        print(f"  {c['method']:7s} {c['path']}")
        for ep in c["endpoints"]:
            print(f"           -> {ep}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
