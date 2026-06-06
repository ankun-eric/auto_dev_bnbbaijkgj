#!/usr/bin/env python3
"""全量链接可达性检查 + 业务测试验证脚本"""
import requests
import json
import sys
import time
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DOMAIN = "6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
BASE_URL = f"https://{DOMAIN}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
TIMEOUT = 15

results = {"pass": [], "fail": [], "issues": [], "stats": {}}

def check_url(url, desc="", expect_status=None, check_content=None):
    """检查单个 URL 的可达性"""
    start = time.time()
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False, allow_redirects=True)
        elapsed = round((time.time() - start) * 1000)
        status = r.status_code
        redirects = [h.url for h in r.history] if r.history else []
        final_url = r.url
        
        content_ok = None
        if check_content:
            content_ok = check_content in r.text
        
        result = {
            "url": url, "desc": desc, "status": status, "elapsed_ms": elapsed,
            "redirects": redirects, "final_url": final_url,
            "content_check": content_ok, "content_expected": check_content,
            "content_length": len(r.text)
        }
        
        if expect_status:
            result["status_match"] = (status == expect_status)
        
        return result
    except requests.exceptions.SSLError as e:
        elapsed = round((time.time() - start) * 1000)
        return {"url": url, "desc": desc, "error": f"SSL Error: {str(e)[:200]}", "elapsed_ms": elapsed}
    except requests.exceptions.ConnectionError as e:
        elapsed = round((time.time() - start) * 1000)
        return {"url": url, "desc": desc, "error": f"Connection Error: {str(e)[:200]}", "elapsed_ms": elapsed}
    except requests.exceptions.Timeout:
        elapsed = round((time.time() - start) * 1000)
        return {"url": url, "desc": desc, "error": "Timeout", "elapsed_ms": elapsed}
    except Exception as e:
        elapsed = round((time.time() - start) * 1000)
        return {"url": url, "desc": desc, "error": f"{type(e).__name__}: {str(e)[:200]}", "elapsed_ms": elapsed}

# ====== Batch 1: 增量优先检查（Bug 修复相关页面） ======
print("=" * 60)
print("Batch 1: 增量优先检查 - Bug 修复相关页面")
print("=" * 60)

incremental_urls = [
    # 管理后台 - 设备管理 (Bug-1&2)
    (f"{BASE_URL}/admin/", "管理后台首页", 200, "设备管理"),
    (f"{BASE_URL}/admin/devices/scene-groups", "设备场景分类页", 200, None),
    (f"{BASE_URL}/admin/devices/catalog", "设备目录管理页", 200, None),
    (f"{BASE_URL}/admin/login", "管理后台登录页", 200, None),
    
    # H5 前端 - Bug 修复页面
    (f"{BASE_URL}/family-auth", "邀请接受页 (Bug-5)", 200, None),
    (f"{BASE_URL}/messages", "系统消息页 (Bug-9)", 200, None),
    (f"{BASE_URL}/health-profile/archive-list", "健康档案列表 (Bug-8)", 200, None),
    (f"{BASE_URL}/health-profile/my-guardians", "我的守护人 (Bug-8)", 200, None),
    
    # API 端点
    (f"{BASE_URL}/api/health", "API 健康检查", 200, None),
    (f"{BASE_URL}/api/messages", "API 消息列表", 200, None),
    
    # 其他相关页面
    (f"{BASE_URL}/", "H5 首页", 200, None),
    (f"{BASE_URL}/ai-home", "AI 首页", 200, None),
    (f"{BASE_URL}/login", "H5 登录页", 200, None),
]

for url, desc, expect_status, content_check in incremental_urls:
    r = check_url(url, desc, expect_status, content_check)
    status_str = f"HTTP {r.get('status','N/A')}"
    if "error" in r:
        status_str = f"ERROR: {r['error'][:100]}"
        results["fail"].append(r)
    elif r.get("status", 0) >= 400:
        results["fail"].append(r)
    else:
        results["pass"].append(r)
    
    content_info = ""
    if r.get("content_check") is not None:
        content_info = f" | 内容检查: {'✓' if r['content_check'] else '✗'}"
    print(f"  [{status_str}] {desc} ({r.get('elapsed_ms',0)}ms){content_info}")

# ====== Batch 2: 关键 API 端点抽样检查 ======
print("\n" + "=" * 60)
print("Batch 2: 关键 API 端点抽样检查")
print("=" * 60)

api_sample_urls = [
    (f"{BASE_URL}/api/auth/login", "用户登录 API (POST 需body)"),
    (f"{BASE_URL}/api/auth/me", "当前用户信息"),
    (f"{BASE_URL}/api/auth/register-settings", "注册设置"),
    (f"{BASE_URL}/api/config/login_ui_version", "登录 UI 版本配置"),
    (f"{BASE_URL}/api/system/server-time", "服务器时间"),
    (f"{BASE_URL}/api/home-menus", "首页菜单"),
    (f"{BASE_URL}/api/home-config", "首页配置"),
    (f"{BASE_URL}/api/home-banners", "首页横幅"),
    (f"{BASE_URL}/api/bottom-nav", "底部导航"),
    (f"{BASE_URL}/api/h5/bottom-nav", "H5 底部导航"),
    (f"{BASE_URL}/api/cities/list", "城市列表"),
    (f"{BASE_URL}/api/cities/hot", "热门城市"),
    (f"{BASE_URL}/api/relation-types", "关系类型"),
    (f"{BASE_URL}/api/family/members", "家庭成员列表"),
    (f"{BASE_URL}/api/family/member/state/list", "成员状态列表"),
    (f"{BASE_URL}/api/reverse-guardian/guardian-count", "守护人数统计"),
    (f"{BASE_URL}/api/reverse-guardian/my-guardians", "我的守护人API"),
    (f"{BASE_URL}/api/devices/catalog", "设备目录"),
    (f"{BASE_URL}/api/devices/my", "我的设备"),
    (f"{BASE_URL}/api/devices/scene-groups", "设备场景分组"),
    (f"{BASE_URL}/api/content/articles", "文章列表"),
    (f"{BASE_URL}/api/content/news/latest", "最新资讯"),
    (f"{BASE_URL}/api/search/hot", "热门搜索"),
    (f"{BASE_URL}/api/ai-home-config", "AI首页配置"),
    (f"{BASE_URL}/api/user/font-setting", "字体设置"),
    (f"{BASE_URL}/api/app-settings/page-style", "页面样式设置"),
    (f"{BASE_URL}/api/chat/function-buttons", "聊天功能按钮"),
    (f"{BASE_URL}/api/chat-sessions/active-check", "聊天活跃检查"),
    (f"{BASE_URL}/api/products/categories", "产品分类"),
    (f"{BASE_URL}/api/products/hot-recommendations", "热门推荐"),
]

for url, desc in api_sample_urls:
    r = check_url(url, desc)
    status = r.get("status", "N/A")
    status_str = f"HTTP {status}"
    if "error" in r:
        status_str = f"ERROR: {r['error'][:80]}"
    
    if isinstance(status, int) and status >= 400:
        results["fail"].append(r)
        status_str += " (FAIL)"
    elif "error" in r:
        results["fail"].append(r)
    else:
        results["pass"].append(r)
    
    print(f"  [{status_str}] {desc} ({r.get('elapsed_ms',0)}ms)")

# ====== Batch 3: 管理后台页面检查 ======
print("\n" + "=" * 60)
print("Batch 3: 管理后台页面抽样检查")
print("=" * 60)

admin_urls = [
    (f"{BASE_URL}/admin/dashboard", "管理后台仪表盘"),
    (f"{BASE_URL}/admin/users", "用户管理"),
    (f"{BASE_URL}/admin/settings", "设置页面"),
    (f"{BASE_URL}/admin/family-management", "家庭管理"),
    (f"{BASE_URL}/admin/function-buttons", "功能按钮管理"),
    (f"{BASE_URL}/admin/health-records", "健康记录"),
    (f"{BASE_URL}/admin/health-records/statistics", "健康记录统计"),
    (f"{BASE_URL}/admin/product-system/products", "产品管理"),
    (f"{BASE_URL}/admin/product-system/orders", "订单管理"),
    (f"{BASE_URL}/admin/product-system/coupons", "优惠券管理"),
    (f"{BASE_URL}/admin/knowledge", "知识库"),
    (f"{BASE_URL}/admin/knowledge/stats", "知识库统计"),
    (f"{BASE_URL}/admin/experts", "专家管理"),
    (f"{BASE_URL}/admin/chat-records", "聊天记录"),
    (f"{BASE_URL}/admin/notices", "公告管理"),
    (f"{BASE_URL}/admin/ai-config", "AI配置"),
    (f"{BASE_URL}/admin/ai-config/chat-timeout", "AI聊天超时配置"),
    (f"{BASE_URL}/admin/ai-center/prompts", "AI中心提示词"),
    (f"{BASE_URL}/admin/ai-center/sensitive-words", "敏感词管理"),
    (f"{BASE_URL}/admin/ai-center/disclaimers", "免责声明"),
    (f"{BASE_URL}/admin/membership/plans", "会员计划"),
    (f"{BASE_URL}/admin/merchant/accounts", "商家账户"),
    (f"{BASE_URL}/admin/merchant/stores", "商家店铺"),
    (f"{BASE_URL}/admin/system/sdk-health", "SDK健康检查"),
    (f"{BASE_URL}/admin/system/seed-import", "种子数据导入"),
    (f"{BASE_URL}/admin/system-messages", "系统消息管理"),
]

for url, desc in admin_urls:
    r = check_url(url, desc)
    status = r.get("status", "N/A")
    status_str = f"HTTP {status}"
    if "error" in r:
        status_str = f"ERROR: {r['error'][:80]}"
    
    if isinstance(status, int) and status >= 400:
        results["fail"].append(r)
        status_str += " (FAIL)"
    elif "error" in r:
        results["fail"].append(r)
    else:
        results["pass"].append(r)
    
    print(f"  [{status_str}] {desc} ({r.get('elapsed_ms',0)}ms)")

# ====== Summary ======
print("\n" + "=" * 60)
print("汇总统计")
print("=" * 60)
pass_count = len(results["pass"])
fail_count = len(results["fail"])
total = pass_count + fail_count
print(f"总计检查: {total}")
print(f"通过: {pass_count} ({100*pass_count/total:.1f}%)" if total > 0 else "通过: 0")
print(f"失败: {fail_count} ({100*fail_count/total:.1f}%)" if total > 0 else "失败: 0")

if fail_count > 0:
    print("\n失败详情:")
    for f in results["fail"]:
        if "error" in f:
            print(f"  ❌ {f['url']}: {f['error'][:150]}")
        else:
            print(f"  ⚠️  {f['url']}: HTTP {f['status']} ({f.get('desc','')})")

# 分类问题
deploy_issues = []
dev_issues = []

for f in results["fail"]:
    if "error" in f:
        if "SSL" in f.get("error", ""):
            deploy_issues.append({
                "type": "部署问题 - SSL", "url": f["url"],
                "desc": f.get("desc", ""), "error": f["error"],
                "diagnosis": "SSL证书验证失败，检查证书配置"
            })
        elif "Connection" in f.get("error", ""):
            deploy_issues.append({
                "type": "部署问题 - 连接失败", "url": f["url"],
                "desc": f.get("desc", ""), "error": f["error"],
                "diagnosis": "服务器不可达或容器未运行"
            })
        elif "Timeout" in f.get("error", ""):
            deploy_issues.append({
                "type": "部署问题 - 超时", "url": f["url"],
                "desc": f.get("desc", ""), "error": f["error"],
                "diagnosis": "服务器响应超时，检查容器负载"
            })
        else:
            deploy_issues.append({
                "type": "部署问题 - 其他", "url": f["url"],
                "desc": f.get("desc", ""), "error": f["error"],
                "diagnosis": "需要进一步诊断"
            })
    else:
        status = f.get("status", 0)
        if status == 502:
            deploy_issues.append({
                "type": "部署问题 - 502", "url": f["url"],
                "desc": f.get("desc", ""), "error": f"HTTP {status}",
                "diagnosis": "后端容器无响应或挂掉"
            })
        elif status == 503:
            deploy_issues.append({
                "type": "部署问题 - 503", "url": f["url"],
                "desc": f.get("desc", ""), "error": f"HTTP {status}",
                "diagnosis": "服务不可用"
            })
        elif status == 404:
            dev_issues.append({
                "type": "开发问题 - 404", "url": f["url"],
                "desc": f.get("desc", ""), "error": f"HTTP {status}",
                "diagnosis": "路径不存在或路由未配置（SPA fallback可能返回200）"
            })
        elif status == 403:
            deploy_issues.append({
                "type": "部署问题 - 403", "url": f["url"],
                "desc": f.get("desc", ""), "error": f"HTTP {status}",
                "diagnosis": "权限被拒绝或需要认证"
            })
        elif status >= 500:
            deploy_issues.append({
                "type": f"部署问题 - {status}", "url": f["url"],
                "desc": f.get("desc", ""), "error": f"HTTP {status}",
                "diagnosis": "服务器内部错误"
            })

print(f"\n部署问题数: {len(deploy_issues)}")
for i, issue in enumerate(deploy_issues, 1):
    print(f"  {i}. [{issue['type']}] {issue['url']} - {issue.get('diagnosis','')}")

print(f"\n开发问题数: {len(dev_issues)}")
for i, issue in enumerate(dev_issues, 1):
    print(f"  {i}. [{issue['type']}] {issue['url']} - {issue.get('diagnosis','')}")

# 输出结构化报告
report = {
    "timestamp": datetime.now().isoformat(),
    "domain": DOMAIN,
    "summary": {
        "total": total,
        "pass": pass_count,
        "fail": fail_count,
        "pass_rate": f"{100*pass_count/total:.1f}%" if total > 0 else "N/A"
    },
    "deploy_issues": deploy_issues,
    "dev_issues": dev_issues,
    "all_results": {
        "pass": results["pass"],
        "fail": results["fail"]
    }
}

with open("C:\\auto_output\\bnbbaijkgj\\test_results.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"\n详细报告已保存到: test_results.json")
sys.exit(0 if fail_count == 0 else 1)
