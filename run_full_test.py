#!/usr/bin/env python3
"""
Full link accessibility test - Phase 4.2
Reads scanned routes, replaces dynamic params, builds URLs, checks with curl.
"""
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

BASE = r"C:\auto_output\bnbbaijkgj"
DOMAIN = "6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"
SSH_PORT = "22"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
CONNECT_TIMEOUT = 5
MAX_TIME = 15
MAX_WORKERS = 15

print_lock = __import__('threading').Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)

def replace_dynamic_params(path):
    """Replace dynamic route parameters with test values."""
    # Next.js style [param] and [...param]
    path = re.sub(r'\[\.\.\.(\w+)\]', r'test-\1', path)
    path = re.sub(r'\[(\w+)\]', r'\1-test', path)
    # FastAPI style {param}
    path = re.sub(r'\{(\w+)\}', r'\1-test', path)
    # Express style :param
    path = re.sub(r':(\w+)', r'\1-test', path)
    return path

def build_url(path, url_type="PAGE"):
    """Build full HTTPS URL."""
    return f"https://{DOMAIN}{path}"

def load_routes():
    """Load scanned routes and build URL list."""
    routes_file = os.path.join(BASE, "scanned_routes.json")
    with open(routes_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    url_list = []
    
    # Backend API routes
    for r in data.get("backend", []):
        path = replace_dynamic_params(r["path"])
        url = build_url(path, "API")
        url_list.append({
            "idx": len(url_list) + 1,
            "type": "API",
            "method": r["method"],
            "url": url,
            "orig_path": r["path"],
            "file": r.get("file", ""),
            "line": r.get("line", 0)
        })
    
    # Admin pages
    for r in data.get("admin", []):
        path = replace_dynamic_params(r["path"])
        url = build_url(path, "PAGE")
        url_list.append({
            "idx": len(url_list) + 1,
            "type": "ADMIN_PAGE",
            "method": "GET",
            "url": url,
            "orig_path": r["path"],
            "file": r.get("file", ""),
            "line": r.get("line", 0)
        })
    
    # H5 pages
    for r in data.get("h5", []):
        path = replace_dynamic_params(r["path"])
        url = build_url(path, "PAGE")
        url_list.append({
            "idx": len(url_list) + 1,
            "type": "H5_PAGE",
            "method": "GET",
            "url": url,
            "orig_path": r["path"],
            "file": r.get("file", ""),
            "line": r.get("line", 0)
        })
    
    return url_list

def curl_check_url(url, method="GET"):
    """Check URL reachability using curl."""
    cmd = [
        "curl", "-Is", "--connect-timeout", str(CONNECT_TIMEOUT),
        "--max-time", str(MAX_TIME),
        "-L", "--max-redirs", "10",
        "-o", "NUL", "-w", "%{http_code}|%{num_redirects}|%{url_effective}"
    ]
    if method != "GET":
        cmd = [
            "curl", "-Is", "-X", method, "--connect-timeout", str(CONNECT_TIMEOUT),
            "--max-time", str(MAX_TIME),
            "-o", "NUL", "-w", "%{http_code}|%{num_redirects}|%{url_effective}"
        ]
    cmd.append(url)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=MAX_TIME+5)
        output = result.stdout.strip()
        parts = output.rsplit("|", 2)
        
        status_code = parts[0] if len(parts) > 0 else "0"
        num_redirects = parts[1] if len(parts) > 1 else "0"
        
        try:
            code_int = int(status_code)
            redirects_int = int(num_redirects)
        except ValueError:
            return {"reachable": False, "status": status_code, "redirects": 0, "error": output[:200]}
        
        if redirects_int >= 10:
            return {"reachable": False, "status": code_int, "redirects": redirects_int, "error": "REDIRECT_LOOP"}
        
        if code_int < 400 or code_int == 405:
            return {"reachable": True, "status": code_int, "redirects": redirects_int, "error": None}
        else:
            return {"reachable": False, "status": code_int, "redirects": redirects_int, "error": f"HTTP {code_int}"}
    
    except subprocess.TimeoutExpired:
        return {"reachable": False, "status": 0, "redirects": 0, "error": "TIMEOUT"}
    except Exception as e:
        return {"reachable": False, "status": 0, "redirects": 0, "error": str(e)[:200]}

def check_ssl():
    """Verify SSL certificate for the domain."""
    cmd = [
        "curl", "-vI", "--connect-timeout", "5", "--max-time", "15",
        f"https://{DOMAIN}/", "-o", "NUL"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        output = result.stderr
        ssl_info = {}
        for line in output.split("\n"):
            if "SSL" in line or "subject" in line.lower() or "issuer" in line.lower() or "expire" in line.lower():
                ssl_info["ssl_ok"] = True
        if "SSL certificate problem" in output:
            ssl_info["ssl_ok"] = False
            ssl_info["ssl_error"] = output[output.index("SSL"):output.index("SSL")+100]
        return ssl_info
    except Exception as e:
        return {"ssl_ok": False, "ssl_error": str(e)}

def check_one(entry):
    """Check one URL and return result."""
    idx = entry["idx"]
    url = entry["url"]
    method = entry["method"]
    result = curl_check_url(url, method)
    result["idx"] = idx
    result["url"] = url
    result["type"] = entry["type"]
    result["method"] = method
    result["file"] = entry.get("file", "")
    result["orig_path"] = entry.get("orig_path", "")
    
    status_str = f"{result['status']} ({result.get('error','')[:30]})" if not result["reachable"] else f"OK {result['status']}"
    safe_print(f"[{idx:4d}] {status_str:40s} {method:6s} {url[:100]}")
    return result

def classify_result(r):
    """Classify result for reporting."""
    if r["reachable"]:
        return "reachable"
    error = r.get("error", "")
    if error == "REDIRECT_LOOP":
        return "redirect_loop"
    if r["status"] == 404:
        return "http_404"
    if r["status"] == 502:
        return "http_502"
    if r["status"] == 503:
        return "http_503"
    if r["status"] == 403:
        return "http_403"
    if r["status"] == 401:
        return "http_401"
    if "TIMEOUT" in str(error):
        return "timeout"
    if r["status"] in (500, 501):
        return "http_5xx"
    if r["status"] >= 400:
        return f"http_{r['status']}"
    return "other_error"

def generate_report(results, url_list, ssl_info):
    """Generate structured test report."""
    total = len(results)
    reachable = [r for r in results if r["reachable"]]
    unreachable = [r for r in results if not r["reachable"]]
    
    # Classify
    by_class = defaultdict(list)
    for r in unreachable:
        cls = classify_result(r)
        by_class[cls].append(r)
    
    # Separate deployment vs development issues
    deploy_issues = []
    dev_issues = []
    
    for r in unreachable:
        cls = classify_result(r)
        url = r["url"]
        rtype = r["type"]
        
        # Classify as deployment or development issue
        if cls == "redirect_loop":
            dev_issues.append({
                "type": "redirect_loop",
                "url": url,
                "route_type": rtype,
                "file": r["file"],
                "diagnosis": "认证跳转竞争或路由守卫导致无限重定向",
                "fix": "检查 layout.tsx / middleware 中的认证逻辑"
            })
        elif cls == "http_404" and rtype in ("H5_PAGE", "ADMIN_PAGE"):
            deploy_issues.append({
                "type": "404_missing_spa_fallback",
                "url": url,
                "route_type": rtype,
                "file": r["file"],
                "diagnosis": "前端页面返回404，缺少 SPA fallback 配置",
                "fix": "检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html"
            })
        elif cls == "http_404" and rtype == "API":
            deploy_issues.append({
                "type": "404_api_route",
                "url": url,
                "route_type": rtype,
                "file": r["file"],
                "diagnosis": "API路由未匹配到 gateway 或未正确注册",
                "fix": "检查 gateway conf.d 配置中的 location 块"
            })
        elif cls == "http_502":
            deploy_issues.append({
                "type": "502_gateway",
                "url": url,
                "route_type": rtype,
                "file": r["file"],
                "diagnosis": "Gateway 无法连接到后端/前端容器",
                "fix": "检查容器是否运行、网络是否配置正确"
            })
        elif cls == "http_503":
            deploy_issues.append({
                "type": "503_service_unavailable",
                "url": url,
                "route_type": rtype,
                "file": r["file"],
                "diagnosis": "服务暂时不可用",
                "fix": "检查容器健康状态和资源使用"
            })
        elif cls == "timeout":
            deploy_issues.append({
                "type": "timeout",
                "url": url,
                "route_type": rtype,
                "file": r["file"],
                "diagnosis": "请求超时，容器可能未启动或响应过慢",
                "fix": "检查容器状态和资源使用"
            })
        else:
            deploy_issues.append({
                "type": cls,
                "url": url,
                "route_type": rtype,
                "file": r["file"],
                "diagnosis": f"HTTP {r['status']}错误",
                "fix": "需要进一步诊断"
            })
    
    # Build report
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("  Noob Test 全量链接检查报告")
    report_lines.append("=" * 70)
    report_lines.append("")
    report_lines.append("部署信息：")
    report_lines.append(f"  项目域名：https://{DOMAIN}")
    report_lines.append(f"  DEPLOY_ID：{DEPLOY_ID}")
    report_lines.append(f"  检查时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    report_lines.append(f"SSL 证书：{'✅ 正常' if ssl_info.get('ssl_ok') else '❌ 异常 - ' + ssl_info.get('ssl_error', '')}")
    report_lines.append("")
    report_lines.append("-" * 70)
    report_lines.append("链接检查统计：")
    report_lines.append(f"  总 URL 数：{total}")
    report_lines.append(f"  ✅ 可达：{len(reachable)} ({len(reachable)/total*100:.1f}%)")
    report_lines.append(f"  ❌ 不可达：{len(unreachable)}")
    
    for cls, items in sorted(by_class.items()):
        report_lines.append(f"    - {cls}：{len(items)}")
    
    report_lines.append("")
    report_lines.append("-" * 70)
    
    if deploy_issues:
        report_lines.append(f"### 部署问题（共 {len(deploy_issues)} 项）")
        report_lines.append("")
        for i, issue in enumerate(deploy_issues, 1):
            report_lines.append(f"  D{i}. [{issue['type']}] {issue['url']}")
            report_lines.append(f"      诊断：{issue['diagnosis']}")
            report_lines.append(f"      修复：{issue['fix']}")
            if issue.get('file'):
                report_lines.append(f"      来源：{issue['file']}")
        report_lines.append("")
    
    if dev_issues:
        report_lines.append(f"### 开发问题（共 {len(dev_issues)} 项）")
        report_lines.append("")
        for i, issue in enumerate(dev_issues, 1):
            report_lines.append(f"  C{i}. [{issue['type']}] {issue['url']}")
            report_lines.append(f"      诊断：{issue['diagnosis']}")
            report_lines.append(f"      修复：{issue['fix']}")
            if issue.get('file'):
                report_lines.append(f"      来源：{issue['file']}")
        report_lines.append("")
    
    report_lines.append("=" * 70)
    
    return {
        "total": total,
        "reachable": len(reachable),
        "unreachable": len(unreachable),
        "by_class": {k: len(v) for k, v in by_class.items()},
        "deploy_issues": deploy_issues,
        "dev_issues": dev_issues,
        "report_text": "\n".join(report_lines),
        "reachable_urls": [r["url"] for r in reachable],
        "unreachable_details": [{"url": r["url"], "status": r["status"], "error": r["error"], "type": r["type"]} for r in unreachable]
    }

def main():
    print("=" * 70)
    print("  Noob Test - Phase 4.1 & 4.2: Route Collection & Link Check")
    print("=" * 70)
    print()
    
    # Phase 4.1: Load routes
    print("[Phase 4.1] Loading scanned routes...")
    url_list = load_routes()
    print(f"  Loaded {len(url_list)} URLs to check")
    
    api_count = sum(1 for u in url_list if u["type"] == "API")
    admin_count = sum(1 for u in url_list if u["type"] == "ADMIN_PAGE")
    h5_count = sum(1 for u in url_list if u["type"] == "H5_PAGE")
    print(f"  - API routes: {api_count}")
    print(f"  - Admin pages: {admin_count}")
    print(f"  - H5 pages: {h5_count}")
    print()
    
    # Phase 4.2: SSL check first
    print("[Phase 4.2] Checking SSL certificate...")
    ssl_info = check_ssl()
    print(f"  SSL: {'OK' if ssl_info.get('ssl_ok') else 'FAILED'}")
    print()
    
    # Phase 4.2: Check URLs in parallel
    # Due to large number of URLs, we check them all in one go with high concurrency
    print(f"[Phase 4.2] Checking {len(url_list)} URLs with {MAX_WORKERS} parallel workers...")
    print()
    
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_one, entry): entry for entry in url_list}
        for future in as_completed(futures):
            try:
                result = future.result(timeout=MAX_TIME+10)
                results.append(result)
            except Exception as e:
                entry = futures[future]
                results.append({
                    "idx": entry["idx"],
                    "url": entry["url"],
                    "type": entry["type"],
                    "method": entry["method"],
                    "reachable": False,
                    "status": 0,
                    "redirects": 0,
                    "error": f"Worker exception: {e}",
                    "file": entry.get("file", "")
                })
    
    # Sort by index
    results.sort(key=lambda r: r["idx"])
    
    # Generate report
    print()
    print("[Phase 4.3] Generating report...")
    report = generate_report(results, url_list, ssl_info)
    
    # Write detailed results
    detailed_path = os.path.join(BASE, "test_results_detailed.json")
    with open(detailed_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    # Write report text
    report_path = os.path.join(BASE, "noob_test_report_20260605.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report["report_text"])
    
    print()
    print(report["report_text"])
    print()
    print(f"Detailed results: {detailed_path}")
    print(f"Report: {report_path}")
    
    return report

if __name__ == "__main__":
    main()
