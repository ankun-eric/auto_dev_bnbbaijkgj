import paramiko, time, sys

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
P=f"/home/{USER}/{DID}"

def run(cli,cmd,t=1800):
    i,o,e=cli.exec_command(cmd,timeout=t)
    out=o.read().decode('utf-8','ignore'); err=e.read().decode('utf-8','ignore')
    code=o.channel.recv_exit_status()
    return code,out,err

cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,username=USER,password=PWD,timeout=30)

# 1) 尝试 git fetch + reset 到最新 master（带重试）
git_ok=False
for i in range(3):
    code,out,err=run(cli, f"cd {P} && timeout 90 git fetch origin master 2>&1", t=120)
    print(f"[fetch try {i+1}] code={code}\n{out}\n{err}")
    if code==0:
        git_ok=True; break
    time.sleep(8)

if git_ok:
    code,out,err=run(cli, f"cd {P} && git reset --hard origin/master 2>&1 && git log -1 --oneline")
    print("[reset]",code,out,err)
else:
    print("[git fetch 失败 -> SFTP 直传改动文件]")
    sftp=cli.open_sftp()
    files=[
        ("h5-web/src/app/(ai-chat)/ai-home/page.tsx", f"{P}/h5-web/src/app/(ai-chat)/ai-home/page.tsx"),
        ("miniprogram/pages/ai/index.js", f"{P}/miniprogram/pages/ai/index.js"),
        ("miniprogram/pages/ai/index.wxml", f"{P}/miniprogram/pages/ai/index.wxml"),
        ("miniprogram/pages/ai/index.wxss", f"{P}/miniprogram/pages/ai/index.wxss"),
        ("backend/tests/test_aihome_scroll_hint_20260602.py", f"{P}/backend/tests/test_aihome_scroll_hint_20260602.py"),
    ]
    import os
    for loc,rem in files:
        sftp.put(loc, rem)
        print("uploaded", rem)
    sftp.close()

# 2) 重建 h5-web（仅 H5 改动了业务代码）。后台 nohup 避免 SSH 流中断。
print("=== building h5-web (no-cache) in background ===")
build_cmd = (f"cd {P} && nohup docker compose -f docker-compose.prod.yml build --no-cache h5-web "
             f"> /tmp/h5_build_scrollhint.log 2>&1 & echo STARTED $!")
code,out,err=run(cli, build_cmd, t=60)
print(out,err)

# 轮询构建日志
for _ in range(60):  # 最长 ~30min
    time.sleep(30)
    code,out,err=run(cli, "tail -3 /tmp/h5_build_scrollhint.log 2>&1")
    print("[build tail]", out.strip()[-300:])
    code2,done,_=run(cli, "grep -lE 'naming to|writing image|DONE|Successfully|ERROR|error:|failed' /tmp/h5_build_scrollhint.log 2>/dev/null; pgrep -f 'compose.*build.*h5-web' >/dev/null && echo RUNNING || echo NOTRUNNING")
    if "NOTRUNNING" in done:
        print("[build finished]")
        break

code,out,err=run(cli, "tail -25 /tmp/h5_build_scrollhint.log")
print("=== build log tail ===\n", out)

# 3) up -d h5-web
code,out,err=run(cli, f"cd {P} && docker compose -f docker-compose.prod.yml up -d --force-recreate h5-web 2>&1", t=300)
print("[up]",code,out,err)

# 4) gateway 重连网络 + reload
code,out,err=run(cli, f"docker network connect {DID}-network gateway-nginx 2>&1; docker exec gateway-nginx nginx -s reload 2>&1; echo RELOAD_DONE")
print("[gateway]",out,err)

cli.close()
print("DEPLOY_SCRIPT_DONE")
