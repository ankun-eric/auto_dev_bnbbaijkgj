"""在 backend 容器内运行前端源码静态断言：先把所需源文件 docker cp 到容器内 _ROOT(/) 对应路径。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BE = f"{DEPLOY_ID}-backend"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30, look_for_keys=False, allow_agent=False)


def run(cmd, timeout=600):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


# 容器内 _ROOT = / ，需要 /h5-web/... 与 /miniprogram/...
copies = [
    (f"{PROJ}/h5-web/src/app/(ai-chat)/ai-home/page.tsx", "/h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
    (f"{PROJ}/miniprogram/pages/ai/index.wxml", "/miniprogram/pages/ai/index.wxml"),
    (f"{PROJ}/miniprogram/pages/ai/index.js", "/miniprogram/pages/ai/index.js"),
    (f"{PROJ}/miniprogram/pages/ai/index.wxss", "/miniprogram/pages/ai/index.wxss"),
]
for src, dst in copies:
    run(f'docker exec {BE} mkdir -p "{dst.rsplit("/",1)[0]}"')
    rc, o, e = run(f'docker cp "{src}" {BE}:"{dst}"')
    print("cp", dst, "rc", rc, e.strip()[:200])

inner = (
    "cd /app && python -m pytest tests/test_ai_home_mode_capsule_v1_20260531.py "
    "-k 'not mode_preference_api_still_works' -v --tb=short 2>&1 | tail -60"
)
cmd = f'docker exec {BE} bash -lc {inner!r}'
rc, out, err = run(cmd)
print(out)
if err.strip():
    print("STDERR:", err[-1500:])
print("RC=", rc)
c.close()
