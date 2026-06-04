import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE=f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=20)
def run(cmd):
    si,so,se = c.exec_command(cmd, timeout=60)
    return so.channel.recv_exit_status(), so.read().decode("utf-8","ignore"), se.read().decode("utf-8","ignore")

# 跟随重定向 + 检查 health-plan 路径
paths = [
    "//health-plan",
    "//health-plan/edit",
    "//health-plan/result",
    "//health-plan/checkin",
    "//api/openapi.json",
]
for path in paths:
    url = f"https://newbb.test.bangbangvip.com{path}"
    rc, out, err = run(f"curl -sL -o /dev/null -w 'HTTP %{{http_code}}  final=%{{url_effective}}  size=%{{size_download}}\\n' --max-time 20 '{url}'")
    print(f"{path}\n  -> {out.strip()}")

# 检查 backend 是否暴露了我们新加的 API
rc, out, err = run(f"curl -s --max-time 20 'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/api/openapi.json' | python3 -c \"import json,sys;d=json.load(sys.stdin);ps=[p for p in d['paths'] if 'checkin' in p or 'health-plan' in p];print('\\n'.join(sorted(ps)))\"")
print("\n=== health-plan / checkin 相关 API ===")
print(out)
c.close()
