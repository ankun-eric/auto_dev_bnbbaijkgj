"""把已上传的 miniprogram zip 复制到正确路径 /static/miniprogram/。"""
import paramiko
HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ROOT = f"/home/ubuntu/{DEPLOY_ID}"

cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
def run(cmd):
    print(f"$ {cmd}")
    _, o, e = cli.exec_command(cmd, timeout=60)
    out = o.read().decode("utf-8", "ignore"); print(out)
    er = e.read().decode("utf-8", "ignore")
    if er.strip(): print("STDERR:", er[:500])
    return out

# 列已上传文件
ls_out = run(f"ls {ROOT}/miniprogram/*.zip 2>/dev/null")
files = [l.strip() for l in ls_out.splitlines() if l.strip().endswith(".zip")]
print("Found zips:", files)

# 准备目标目录
run(f"mkdir -p {ROOT}/static/miniprogram/")

for f in files:
    name = f.rsplit("/", 1)[-1]
    run(f"cp -v {f} {ROOT}/static/miniprogram/{name}")
    run(f"chmod 644 {ROOT}/static/miniprogram/{name}")

# 验证
for f in files:
    name = f.rsplit("/", 1)[-1]
    url = f"https://{HOST}/autodev/{DEPLOY_ID}/miniprogram/{name}"
    run(f'curl -s -o /dev/null -w "{name} -> %{{http_code}}\\n" "{url}"')
cli.close()
