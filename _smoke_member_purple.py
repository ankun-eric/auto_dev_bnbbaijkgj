from _ssh_helper import run, DEPLOY_ID
urls = [
    f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/member-center/",
    f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/health-profile/",
    f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/member/center",
    f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/member/quota-usage",
]
for u in urls:
    rc, out, err = run(f"curl -s -o /dev/null -w 'HTTP %{{http_code}}\\n' '{u}'", timeout=20)
    print(f"  {u} -> {out.strip()}")

# 检查内容关键字
rc, out, err = run(
    f"docker exec {DEPLOY_ID}-h5 sh -lc \"grep -l '5B6CFF' /app/.next/static/chunks/app/member-center/*.js | head\"",
    timeout=30,
)
print("chunk 5B6CFF =>", out)

rc, out, err = run(
    f"docker exec {DEPLOY_ID}-h5 sh -lc \"grep -l 'paid_normal' /app/.next/static/chunks/app/member-center/*.js | head\"",
    timeout=30,
)
print("chunk paid_normal =>", out)

rc, out, err = run(
    f"docker exec {DEPLOY_ID}-h5 sh -lc \"grep -l '蓝紫' /app/.next/server/app/member-center/page.js | head\"",
    timeout=30,
)
print("server 蓝紫 =>", out)
