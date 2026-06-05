"""关键 URL 精确检查 - 使用 GET 方法，追踪重定向链。"""
import subprocess
import json
import sys

BASE_URL = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

def check_get(url, follow=True, timeout=20):
    """GET 请求检查，返回详细信息。"""
    try:
        cmd = [
            "curl", "-s", "-o", "NUL",
            "-w", "%{http_code}|%{redirect_url}|%{url_effective}|%{time_total}|%{size_download}",
            "--connect-timeout", "5",
            "--max-time", str(timeout),
            "-X", "GET",
        ]
        if follow:
            cmd.append("-L")
        cmd.append(url)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
        output = result.stdout.strip()
        parts = output.split("|")
        
        return {
            "url": url,
            "status": int(parts[0]) if parts[0].isdigit() else 0,
            "redirect_url": parts[1] if len(parts) > 1 else "",
            "final_url": parts[2] if len(parts) > 2 else "",
            "time": parts[3] if len(parts) > 3 else "",
            "size": parts[4] if len(parts) > 4 else "",
        }
    except Exception as e:
        return {"url": url, "status": 0, "error": str(e)}

def check_full_chain(url, timeout=20):
    """检查完整重定向链。"""
    try:
        cmd = [
            "curl", "-s", "-o", "NUL",
            "-w", "HTTP_STATUS:%{http_code} URL:%{url_effective} REDIRECT:%{redirect_url}\n",
            "--connect-timeout", "5",
            "--max-time", str(timeout),
            "-L", "-X", "GET",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"

print("=" * 60)
print("关键 URL 精确检查 (GET 方法)")
print("=" * 60)

# 需要特别验证的接口
api_endpoints = [
    # 已删除的接口 - 应该返回 404
    ("DELETE_CHECK", f"{BASE_URL}/api/care-v1/home/welcome"),
    ("DELETE_CHECK", f"{BASE_URL}/api/care-v1/home/proactive-cards"),
    ("DELETE_CHECK", f"{BASE_URL}/api/care-v1/sos/events"),
    ("DELETE_CHECK", f"{BASE_URL}/api/care-v1/sos/keywords"),
    # 应正常可用的接口
    ("ACTIVE_CHECK", f"{BASE_URL}/api/care-v1/user-preferences"),
    # 新增的接口
    ("NEW_CHECK", f"{BASE_URL}/api/care/alerts/active"),
    ("NEW_CHECK", f"{BASE_URL}/api/care/daily-summary"),
    # 健康检查
    ("HEALTH", f"{BASE_URL}/api/health"),
]

print("\n--- API 端点 (GET 不跟随重定向) ---")
for label, url in api_endpoints:
    r = check_get(url, follow=False)
    status = r['status']
    flag = ""
    if status == 404:
        flag = " ✅ 404 (已删除正确)"
    elif status == 200:
        flag = " ✅ 200 (正常)"
    elif status == 401 or status == 403:
        flag = f" ⚠️ {status} (需认证，接口存在)"
    elif status == 405:
        flag = f" ⚠️ 405 (方法不允许，接口存在)"
    elif status == 0:
        flag = f" ❌ 连接失败: {r.get('error', '')}"
    else:
        flag = f" ⚠️ {status}"
    print(f"  [{label}] {r['url']} -> {status}{flag}")

# 前端页面检查 - 重定向链
print("\n--- 前端页面 (GET 跟随重定向) ---")
frontend_pages = [
    ("CARE_HOME_REDIRECT", f"{BASE_URL}/care-home"),
    ("CARE_AI_HOME", f"{BASE_URL}/care-ai-home"),
    ("CARE_AI_SOS", f"{BASE_URL}/care-ai-home/sos"),
    ("CARE_AI_TODAY", f"{BASE_URL}/care-ai-home/today-health"),
    ("CARE_AI_INFO", f"{BASE_URL}/care-ai-home/info-card"),
    ("SAFETY_ROPE", f"{BASE_URL}/care-safety-rope"),
    ("HOME_SAFETY", f"{BASE_URL}/home-safety"),
    ("AI_HOME_REDIRECT", f"{BASE_URL}/ai-home"),
    ("HOME_REDIRECT", f"{BASE_URL}/home"),
    ("ROOT", f"{BASE_URL}/"),
    ("LOGIN", f"{BASE_URL}/login"),
]

for label, url in frontend_pages:
    # First get direct status
    r_direct = check_get(url, follow=False)
    r_follow = check_get(url, follow=True)
    
    direct_status = r_direct['status']
    final_status = r_follow['status']
    final_url = r_follow.get('final_url', '')
    redirect = r_direct.get('redirect_url', '')
    
    flag = ""
    if direct_status in (301, 302, 307, 308):
        flag = f" -> [{final_status}] {final_url}"
        if label == "CARE_HOME_REDIRECT":
            if "care-ai-home" in final_url.lower():
                flag += " ✅ 正确重定向到 care-ai-home"
            else:
                flag += " ❌ 未重定向到 care-ai-home"
        elif label == "HOME_REDIRECT":
            if "ai-home" in final_url.lower():
                flag += " ✅ 正确重定向到 ai-home"
            else:
                flag += " ❌ 未重定向到 ai-home"
        elif label == "AI_HOME_REDIRECT":
            if "ai-home" in final_url.lower():
                flag += " ✅ 正确重定向到 ai-home"
            else:
                flag += " ❌ 未重定向到 ai-home"
    elif direct_status == 200:
        flag = f" ✅ 200 (直接返回)"
    elif direct_status == 404:
        flag = " ❌ 404 (页面不存在)"
    else:
        flag = f" ⚠️ {direct_status}"
    
    print(f"  [{label}] {url}: {direct_status}{flag}")
    if redirect:
        print(f"          Redirect: {redirect}")

# 重定向链详细追踪
print("\n--- 重定向链详细追踪 ---")
for label, url in frontend_pages:
    chain = check_full_chain(url)
    print(f"  [{label}] {url}")
    print(f"          {chain}")

print("\nDone!")
