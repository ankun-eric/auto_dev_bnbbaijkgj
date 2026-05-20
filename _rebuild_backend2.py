"""rebuild backend: sync 我们改过的源文件到 host，然后 docker compose build"""
import paramiko, time, os, sys, tarfile, io
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE=f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"
REMOTE=f"/home/ubuntu/{DEPLOY_ID}"

BACKEND_FILES = [
    "backend/app/services/prd_tcm36_drawer_v12_migration.py",
    "backend/app/services/prd_questionnaire_drawer_v1_migration.py",
    "backend/app/services/prd_qn_content_v1_migration.py",
    "backend/app/services/prd_tag_recommend_v1_migration.py",
    "backend/app/services/seed_packs/__init__.py",
    "backend/app/services/seed_packs/registry.py",
    "backend/app/api/seed_import.py",
    "backend/app/main.py",
    "backend/scripts/cleanup_tcm_orphan_template.py",
    "backend/tests/test_ai_page_optim_v1_20260521.py",
]

cli=paramiko.SSHClient();cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com",username="ubuntu",password="Newbang888",timeout=120)
sftp=cli.open_sftp()

def sh(c,t=900):
    si,so,se=cli.exec_command(c,timeout=t)
    return so.read().decode(errors='replace'),se.read().decode(errors='replace'),so.channel.recv_exit_status()

# 打包上传
print("打包...")
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w:gz') as tf:
    for rel in BACKEND_FILES:
        local=os.path.join(os.getcwd(),rel.replace('/',os.sep))
        if not os.path.exists(local):
            print(f"  [warn] 本地缺失:{rel}");continue
        tf.add(local,arcname=rel)
buf.seek(0)
remote_tar=f"{REMOTE}/_ai_page_optim_be.tar.gz"
with sftp.open(remote_tar,'wb') as fp:
    fp.write(buf.getvalue())
print(f"上传完成,size={buf.tell()}")
sftp.close()

# 解压（覆盖到 host）
o,e,c=sh(f"cd {REMOTE} && tar xzf _ai_page_optim_be.tar.gz && rm _ai_page_optim_be.tar.gz && echo done")
print("解压:",o.strip()[:200])

# 校验 host 上 seed_import.py 已就位
o,_,_=sh(f"ls -la {REMOTE}/backend/app/api/seed_import.py {REMOTE}/backend/app/services/seed_packs/")
print("host 文件:",o.strip())

# rebuild backend
print("\n=== docker compose build backend ===")
o,e,c=sh(f"cd {REMOTE} && docker compose build backend 2>&1 | tail -30",t=900)
print(o);print("[exit]",c)

print("\n=== docker compose up -d backend ===")
o,e,c=sh(f"cd {REMOTE} && docker compose up -d backend 2>&1",t=120)
print(o.strip())

print("等待 20 秒迁移...");time.sleep(20)

# 检查路由是否注册
o,_,_=sh(f"curl -s --max-time 15 '{BASE}/api/openapi.json' | python3 -c 'import sys,json;d=json.load(sys.stdin);print([p for p in d.get(\"paths\",{{}}).keys() if \"seed-packs\" in p])'")
print("openapi seed-packs paths:",o.strip())

o,_,_=sh(f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 15 '{BASE}/api/admin/seed-packs'")
print("/api/admin/seed-packs no auth status:",o.strip(),"(期望401/403)")

# backend 日志查迁移行为（应该都是 skipped）
o,_,_=sh(f"docker logs --tail 80 {DEPLOY_ID}-backend 2>&1 | grep -E '(skipped|seed_skip|tcm36|qn_content|tag_recommend)' | tail -20")
print("--- 迁移 skip 日志 ---");print(o)

cli.close()
