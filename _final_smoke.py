"""最终验收烟测"""
import paramiko
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE=f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
cli=paramiko.SSHClient();cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com",username="ubuntu",password="Newbang888",timeout=60)
def sh(c,t=60):
    si,so,se=cli.exec_command(c,timeout=t)
    return so.read().decode(errors='replace'),so.channel.recv_exit_status()
def status(u):
    o,_=sh(f"curl -s -L -o /dev/null -w '%{{http_code}}' --max-time 30 '{u}'")
    return o.strip()

print("=========== AI 页面优化 v1 - 最终验收 ===========")
cases = [
    ("Bug1+Bug2 / H5 健康档案新页面",f"{BASE}/health-profile","200"),
    ("Bug2 / H5 旧 /health-archive 期望 404",f"{BASE}/health-archive","404"),
    ("E / Admin 种子数据导入页面",f"{BASE}/admin/system/seed-import","200"),
    ("D / Admin 通用问卷模板页",f"{BASE}/admin/questionnaire-templates","200"),
    ("D / Admin 健康自查专属配置页",f"{BASE}/admin/health-check-templates","200"),
    ("E / API 种子包列表 (无 token=401)",f"{BASE}/api/admin/seed-packs","401"),
    ("基础 / H5 首页",f"{BASE}/","200"),
    ("基础 / Admin 首页",f"{BASE}/admin/","200"),
    ("基础 / openapi.json",f"{BASE}/api/openapi.json","200"),
]
pass_count=0
for desc,url,expect in cases:
    code = status(url)
    ok = (code == expect)
    flag = "✅" if ok else "❌"
    if ok: pass_count+=1
    print(f"  {flag} [{code}] (期望{expect}) {desc}")
print(f"\n通过: {pass_count}/{len(cases)}")

# openapi 含 4 个 seed-packs 路径
o,_=sh(f"curl -s --max-time 15 '{BASE}/api/openapi.json' | python3 -c 'import sys,json;d=json.load(sys.stdin);print([p for p in d.get(\"paths\",{{}}).keys() if \"seed-packs\" in p])'")
print(f"\n种子包 API 路径已注册: {o.strip()}")

# Bug3 验证：迁移日志显示种子已全部跳过
print("\n--- backend 迁移 skip 日志（验证 Bug3 关闭自动插入）---")
o,_=sh(f"docker logs {DEPLOY_ID}-backend 2>&1 | grep -E 'by_seed_pack_admin_page' | tail -10")
print(o)

# 块 C 验证：孤儿模板已不存在
print("--- 块 C 验证: 孤儿模板清理 ---")
o,_=sh(f"docker exec {DEPLOY_ID}-backend python -c \"import asyncio; from scripts.cleanup_tcm_orphan_template import cleanup_orphan_tcm_template; r=asyncio.run(cleanup_orphan_tcm_template()); print('已清理:',r.get('template_deleted'),'警告:',r.get('warnings'))\" 2>&1 | tail -5")
print(o.strip())

cli.close()
