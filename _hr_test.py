import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DIR = "/home/ubuntu/%s" % DEPLOY_ID
BE = "%s-backend" % DEPLOY_ID
BASE = "https://newbb.test.bangbangvip.com/autodev/%s" % DEPLOY_ID

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, t=600):
    print("\n$ " + cmd[:140])
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip(): print(out.strip()[-4000:])
    if err.strip(): print("[stderr] " + err.strip()[-1500:])
    print("[exit %d]" % code)
    return code

# 把测试文件拷进 backend 容器并运行
run("docker cp %s/backend/tests/test_hr_align_bp_v1_20260601.py %s:/app/tests/test_hr_align_bp_v1_20260601.py" % (DIR, BE))
# 前端静态断言测试依赖 h5-web / miniprogram 源码路径，容器内没有；这些已在本地通过。
# 这里只跑后端心率 CRUD 回归用例（按测试函数名筛选）
run("docker exec %s sh -c 'cd /app && python -m pytest tests/test_hr_align_bp_v1_20260601.py -k \"hr_create or hr_put or hr_delete\" -p no:cacheprovider -q 2>&1' | tail -40" % BE, t=600)

print("\n=== LINK CHECKS ===")
links = [
    "%s/health-profile" % BASE,
    "%s/health-metric/heart_rate" % BASE,
    "%s/health-metric/blood_pressure" % BASE,
    "%s/health-metric/blood_glucose" % BASE,
    "%s/api/health" % BASE,
]
for u in links:
    run("curl -s -o /dev/null -w '%%{http_code}' -L '%s'" % u)

c.close()
