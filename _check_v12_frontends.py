"""[守护人体系 PRD v1.2] 校验前端页面可访问 - 通过域名网关"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

# H5: basePath=/autodev/{DEPLOY_ID}（无 /h5 中间段），admin 同理
H5_PATHS = ["/health-profile/i-guard", "/member-center", "/ai-home"]
ADMIN_PATHS = ["/admin/emergency-sources", "/admin/family-management"]
API_PATHS = [
    "/api/openapi.json",
    "/api/guardian/v12/i-guard",
    "/api/admin/emergency-sources",
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PWD, timeout=30)


def hit(path):
    cmd = (
        f"curl -sk -L -o /tmp/r.txt -w '{path} → HTTP %{{http_code}}, size=%{{size_download}}\\n' "
        f"'{BASE_URL}{path}'"
    )
    i, o, _ = client.exec_command(cmd, timeout=20)
    print(o.read().decode("utf-8", errors="replace").strip())


print("[H5 页面]")
for p in H5_PATHS:
    hit(p)
print("\n[admin-web 页面]")
for p in ADMIN_PATHS:
    hit(p)
print("\n[API 端点]")
for p in API_PATHS:
    hit(p)
client.close()
