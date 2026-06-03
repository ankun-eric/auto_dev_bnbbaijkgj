import paramiko, time

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
P=f"/home/{USER}/{DID}"

def run(cli,cmd,t=120):
    i,o,e=cli.exec_command(cmd,timeout=t)
    out=o.read().decode('utf-8','ignore'); err=e.read().decode('utf-8','ignore')
    code=o.channel.recv_exit_status()
    return code,out,err

cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,username=USER,password=PWD,timeout=30)

# 是否已有 build 在跑？
code,out,err=run(cli, "pgrep -f 'compose.*build' >/dev/null && echo RUNNING || echo NONE")
print("[state]", out.strip())

if "NONE" in out:
    # 用 setsid 完全脱离会话启动后台构建
    start = (f"cd {P} && setsid bash -c 'docker compose -f docker-compose.prod.yml build --no-cache h5-web "
             f"> /tmp/h5_build_sh.log 2>&1' < /dev/null & echo OK")
    code,out,err=run(cli, start, t=30)
    print("[start build]", out.strip(), err.strip())
    time.sleep(5)
    code,out,err=run(cli, "tail -2 /tmp/h5_build_sh.log 2>&1; pgrep -f 'compose.*build' >/dev/null && echo RUNNING || echo NONE")
    print("[after start]", out.strip())

cli.close()
print("STEP2_DONE")
