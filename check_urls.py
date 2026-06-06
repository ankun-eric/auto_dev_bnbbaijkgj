import requests, urllib3
urllib3.disable_warnings()
D = "6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

urls = [
    (f"https://{D}/health-profile", "健康档案首页"),
    (f"https://{D}/health-profile/i-guard", "我守护的"),
    (f"https://{D}/health-profile/my-guardians/invite", "邀请守护人"),
    (f"https://{D}/health-profile/v13", "健康档案v13"),
    (f"https://{D}/family-invite", "家庭邀请"),
    (f"https://{D}/family-bindlist", "家庭绑定列表"),
    (f"https://{D}/family-guardian-list", "家庭守护列表"),
    (f"https://{D}/family-alert", "家庭提醒"),
    (f"https://{D}/family", "家庭页面"),
    (f"https://{D}/health-plan", "健康计划"),
    (f"https://{D}/health-dashboard", "健康仪表盘"),
    (f"https://{D}/medical-records", "医疗记录"),
    (f"https://{D}/devices", "设备页面"),
    (f"https://{D}/care-ai-home", "关怀AI首页"),
    (f"https://{D}/care-safety-rope", "安全绳索"),
    (f"https://{D}/api/public/protocol/privacy-policy", "隐私政策"),
    (f"https://{D}/api/public/protocol/service-agreement", "服务协议"),
    (f"https://{D}/api/captcha/image", "验证码图片"),
    (f"https://{D}/api/health-alerts", "健康提醒列表"),
    (f"https://{D}/api/notices/active", "活跃公告"),
    (f"https://{D}/api/health-reminders/recommendations", "健康提醒推荐"),
    (f"https://{D}/api/v2/app/version-check", "APP版本检查"),
    (f"https://{D}/api/app-settings/chat-idle-timeout", "聊天空闲超时"),
    (f"https://{D}/api/care-card/public/test", "关怀卡公共页面"),
    (f"https://{D}/api/constitution/encyclopedia/qi_deficiency", "中医体质百科"),
]

for url, desc in urls:
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, verify=False)
        print(f"[HTTP {r.status_code}] {desc} | Size: {len(r.text)} bytes | URL: {url}")
    except Exception as e:
        print(f"[ERROR] {desc} | {type(e).__name__}: {str(e)[:100]}")
