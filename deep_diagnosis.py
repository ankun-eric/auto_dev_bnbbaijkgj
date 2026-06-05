"""深度诊断：GET 方法测试 API + SSH 检查配置。"""
import subprocess
import json
import paramiko
import sys

BASE_URL = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def curl_get(url, timeout=15):
    """GET 请求（不跟随重定向）。"""
    try:
        cmd = [
            "curl", "-s", "-o", "NUL",
            "-w", "%{http_code}|%{size_download}|%{time_total}",
            "--connect-timeout", "5",
            "--max-time", str(timeout),
            "-X", "GET",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
        parts = result.stdout.strip().split("|")
        return {
            "status": int(parts[0]) if parts[0].isdigit() else 0,
            "size": parts[1] if len(parts) > 1 else "",
            "time": parts[2] if len(parts) > 2 else ""
        }
    except Exception as e:
        return {"status": 0, "error": str(e)}

# ═══════════════════════════════
# 1. GET 方法测试关键 API
# ═══════════════════════════════
print("=" * 60)
print("1. GET 方法测试关键 API")
print("=" * 60)

api_tests = [
    # 据称已删除的 care-v1 接口
    ("care-v1 welcome (应删除)", f"{BASE_URL}/api/care-v1/home/welcome", 404),
    ("care-v1 proactive-cards (应删除)", f"{BASE_URL}/api/care-v1/home/proactive-cards", 404),
    ("care-v1 sos/events (应删除)", f"{BASE_URL}/api/care-v1/sos/events", 404),
    ("care-v1 sos/keywords (应删除)", f"{BASE_URL}/api/care-v1/sos/keywords", 404),
    # 应正常可用的
    ("care-v1 user-preferences", f"{BASE_URL}/api/care-v1/user-preferences", None),
    ("care alerts/active (新)", f"{BASE_URL}/api/care/alerts/active", None),
    ("care daily-summary (新)", f"{BASE_URL}/api/care/daily-summary", None),
    ("health check", f"{BASE_URL}/api/health", 200),
    # 其他随机抽样
    ("family members", f"{BASE_URL}/api/family/members", None),
    ("auth me", f"{BASE_URL}/api/auth/me", None),
    ("health profile", f"{BASE_URL}/api/health/profile", None),
    ("home config", f"{BASE_URL}/api/home-config", None),
    ("ai-home config", f"{BASE_URL}/api/ai-home-config", None),
    ("cards wallet", f"{BASE_URL}/api/cards/me/wallet", None),
    ("member center", f"{BASE_URL}/api/member/center", None),
    ("products categories", f"{BASE_URL}/api/products/categories", None),
    ("points balance", f"{BASE_URL}/api/points/balance", None),
    ("notices active", f"{BASE_URL}/api/notices/active", None),
    ("messages", f"{BASE_URL}/api/messages", None),
    ("ai-call quota", f"{BASE_URL}/api/ai-call/quota", None),
]

for label, url, expected in api_tests:
    r = curl_get(url)
    status = r['status']
    match = ""
    if expected and status == expected:
        match = " ✅ 符合预期"
    elif expected and status != expected:
        match = f" ❌ 预期 {expected}，实际 {status}"
    elif status == 200:
        match = " ✅ 正常"
    elif status == 401 or status == 403:
        match = " ⚠️ 需认证（接口存在）"
    elif status == 404:
        match = " ⚠️ 404 不存在"
    elif status == 0:
        match = f" ❌ 连接失败: {r.get('error', '')}"
    else:
        match = f" ⚠️ 状态码 {status}"
    print(f"  [{status:3d}] {label}: {url}{match}")

# ═══════════════════════════════
# 2. SSH 深入诊断
# ═══════════════════════════════
print("\n" + "=" * 60)
print("2. SSH 深入诊断")
print("=" * 60)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace')

# 2a. 检查 care-home 页面是否有重定向配置
print("\n--- 2a. care-home 重定向配置 ---")
# Check routes-manifest redirects
out = run(f'docker exec {DEPLOY_ID}-h5 cat /app/.next/routes-manifest.json 2>/dev/null')
try:
    manifest = json.loads(out)
    redirects = manifest.get('redirects', [])
    care_home_redirect = [r for r in redirects if 'care-home' in r.get('source', '') or 'care-home' in r.get('destination', '')]
    print(f"care-home 相关重定向: {json.dumps(care_home_redirect, indent=2) if care_home_redirect else '未找到'}")
except:
    print("无法解析 routes-manifest")

# 2b. 检查后端 care-v1 路由是否仍存在
print("\n--- 2b. 后端 care-v1 路由检查 ---")
out = run(f'docker exec {DEPLOY_ID}-backend grep -rn "care-v1" /app/app/api/ --include="*.py" 2>/dev/null | head -30')
print(f"care-v1 路由引用:\n{out[:2000] if out else '未找到任何 care-v1 引用'}")

# 2c. 检查 ai_home_care_v1.py 文件
print("\n--- 2c. ai_home_care_v1.py 路由定义 ---")
out = run(f'docker exec {DEPLOY_ID}-backend grep -n \"@.*router\\.\" /app/app/api/ai_home_care_v1.py 2>/dev/null | head -20')
print(out if out else "文件不存在或无路由装饰器")

# 也检查这个文件的 include_router
out = run(f'docker exec {DEPLOY_ID}-backend grep -rn \"ai_home_care_v1\" /app/app/main.py 2>/dev/null')
print(f"main.py 中的引用: {out if out else '未在 main.py 中找到'}")

# 2d. 检查 care_ai_home.py (新的替代文件)
print("\n--- 2d. care_ai_home.py 路由定义 ---")
out = run(f'docker exec {DEPLOY_ID}-backend grep -n \"@.*router\\.\" /app/app/api/care_ai_home.py 2>/dev/null | head -20')
print(out if out else "文件不存在或无路由装饰器")

# 2e. 检查新的 /api/care 路由
print("\n--- 2e. /api/care 路由检查 ---")
out = run(f'docker exec {DEPLOY_ID}-backend grep -rn \"prefix.*care\" /app/app/api/care_ai_home.py 2>/dev/null')
print(f"care_ai_home.py prefix: {out[:500] if out else '未找到'}")

# 2f. 检查 care-safety-rope 页面内容
print("\n--- 2f. care-safety-rope 页面元素 ---")
out = run(f'docker exec {DEPLOY_ID}-h5 ls -la /app/.next/server/app/care-safety-rope 2>/dev/null')
print(f"care-safety-rope 构建文件: {out[:500] if out else '未找到'}")

# 2g. 检查 care-ai-home 页面构建文件
print("\n--- 2g. care-ai-home 相关页面 ---")
out = run(f'docker exec {DEPLOY_ID}-h5 find /app/.next/server/app/care-ai-home -type f 2>/dev/null')
print(f"care-ai-home 构建文件:\n{out[:1500] if out else '未找到'}")

out = run(f'docker exec {DEPLOY_ID}-h5 find /app/.next/server/app/care-home -type f 2>/dev/null')
print(f"care-home 构建文件:\n{out[:1000] if out else '未找到'}")

# 2h. 检查 /api/care-v1/user-preferences/ui-mode 路由
print("\n--- 2h. user-preferences/ui-mode 路由 ---")
out = run(f'docker exec {DEPLOY_ID}-backend grep -n \"ui.mode\\|ui_mode\" /app/app/api/ai_home_care_v1.py 2>/dev/null')
print(f"ui-mode 路由: {out[:500] if out else '未找到'}")

# 也检查 user_mode_preference.py
out = run(f'docker exec {DEPLOY_ID}-backend grep -rn \"user.preference\\|user_mode\" /app/app/api/user_mode_preference.py 2>/dev/null | head -20')
print(f"user_mode_preference.py: {out[:1000] if out else '文件不存在'}")

ssh.close()
print("\n诊断完成!")
