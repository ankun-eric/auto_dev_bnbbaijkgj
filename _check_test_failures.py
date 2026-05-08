import paramiko, time

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND=f"{DID}-backend"

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

cmd = (
    f"docker exec {BACKEND} sh -c "
    "'cd /app && python -m pytest tests/test_bugfix_merchant_reschedule_v1.py -v --tb=long 2>&1 | tail -200'"
)

chan=c.get_transport().open_session(); chan.get_pty()
chan.exec_command(cmd)
out=b''
last=time.time()
while True:
    if chan.recv_ready():
        out+=chan.recv(65535); last=time.time()
    if chan.exit_status_ready() and not chan.recv_ready(): break
    if time.time()-last>120: break
    time.sleep(0.3)
print(out.decode('utf-8',errors='ignore'))
c.close()
