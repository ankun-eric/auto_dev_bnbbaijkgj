import paramiko, sys, time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting...", flush=True)
try:
    ssh.connect("newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888", timeout=15)
    print("Connected!", flush=True)
except Exception as e:
    print(f"Connect failed: {e}", flush=True)
    sys.exit(1)

print("Running hostname...", flush=True)
try:
    stdin, stdout, stderr = ssh.exec_command("hostname", timeout=10)
    out = stdout.read().decode()
    err = stderr.read().decode()
    ec = stdout.channel.recv_exit_status()
    print(f"hostname: out='{out.strip()}' err='{err.strip()}' rc={ec}", flush=True)
except Exception as e:
    print(f"hostname failed: {e}", flush=True)

ssh.close()
print("Done", flush=True)
