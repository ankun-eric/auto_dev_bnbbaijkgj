import paramiko, time

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
P=f"/home/{USER}/{DID}"

def run(cli,cmd,t=300):
    i,o,e=cli.exec_command(cmd,timeout=t)
    out=o.read().decode('utf-8','ignore'); err=e.read().decode('utf-8','ignore')
    code=o.channel.recv_exit_status()
    return code,out,err

cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,username=USER,password=PWD,timeout=30)

LOG="/tmp/h5_build_scrollhint.log"  # 之前 nohup 写入的日志
finished=False
for _ in range(50):
    time.sleep(30)
    code,out,err=run(cli, f"tail -2 {LOG} 2>/dev/null; echo ---; pgrep -f 'compose.*build' >/dev/null && echo RUNNING || echo NONE")
    print("[tail]", out.strip()[-260:])
    if "NONE" in out:
        finished=True; break

code,out,err=run(cli, f"tail -20 {LOG}")
print("=== final build log ===\n", out)
cli.close()
print("WAIT_DONE finished=",finished)
