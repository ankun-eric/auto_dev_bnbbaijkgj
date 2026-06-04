import paramiko, time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30,
               look_for_keys=False, allow_agent=False)

def run(cmd, timeout=120):
    chan = client.get_transport().open_session()
    chan.exec_command(cmd)
    out = b""
    err = b""
    deadline = time.time() + timeout
    while not chan.exit_status_ready():
        if time.time() > deadline:
            break
        if chan.recv_ready():
            out += chan.recv(65536)
        if chan.recv_stderr_ready():
            err += chan.recv_stderr(65536)
        time.sleep(0.1)
    try:
        out += chan.recv(65536)
    except:
        pass
    try:
        err += chan.recv_stderr(65536)
    except:
        pass
    result = out.decode(errors='replace')
    if err:
        e = err.decode(errors='replace').strip()
        if e:
            print(f"  [stderr]: {e[:500]}")
    return result, chan.exit_status

print("Running bucket migration with -y flag...")
out, ec = run(f"docker exec {DEPLOY_ID}-backend python /app/migrations/migration_bucket_replace_20260604.py -y 2>&1", timeout=120)
print(out)
print(f"\nExit code: {ec}")

if ec == 0:
    print("\n=== Migration SUCCESS ===")
else:
    print("\n=== Migration FAILED ===")
    # Try rollback
    print("Attempting rollback...")
    out, ec = run(f"docker exec {DEPLOY_ID}-backend python /app/migrations/migration_bucket_replace_20260604.py --rollback -y 2>&1", timeout=120)
    print(out)

client.close()
