import paramiko
HOST="newbb.test.bangbangvip.com";PORT=22;USER="ubuntu";PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
def run(c,cmd,t=600):
    print(f"\n$ {cmd[:200]}")
    _,so,se=c.exec_command(cmd,timeout=t+30,get_pty=False)
    so.channel.settimeout(t+30);se.channel.settimeout(t+30)
    out=so.read().decode();err=se.read().decode()
    rc=so.channel.recv_exit_status()
    if out.strip(): print(out[-4500:])
    if err.strip(): print("STDERR:",err[-1500:])
    return rc
cli=paramiko.SSHClient();cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,PORT,USER,PWD,timeout=30,allow_agent=False,look_for_keys=False)
try:
    run(cli,f"docker exec {DID}-backend pip install -q aiosqlite 2>&1 | tail -3")
    run(cli,f"docker exec {DID}-backend python -m pytest tests/test_health_archive_optim_v1_20260518.py -v --no-header 2>&1 | tail -120",t=600)
finally:
    cli.close()
