import paramiko
import sys

print("Starting...", flush=True)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print("Connecting...", flush=True)
    ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)
    print("Connected!", flush=True)
    
    print("Running docker ps...", flush=True)
    stdin, stdout, stderr = ssh.exec_command('docker ps --format "{{.Names}}"', timeout=15)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print("STDOUT:", repr(out), flush=True)
    print("STDERR:", repr(err), flush=True)
    
    ssh.close()
    print("Done!", flush=True)
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
