import paramiko
import sys
import time

host = sys.argv[1] if len(sys.argv) > 1 else 'newbb.test.bangbangvip.com'
port = int(sys.argv[2]) if len(sys.argv) > 2 else 22
user = sys.argv[3] if len(sys.argv) > 3 else 'ubuntu'
password = sys.argv[4] if len(sys.argv) > 4 else 'Newbang888'
cmd = sys.argv[5] if len(sys.argv) > 5 else 'echo OK'
timeout = int(sys.argv[6]) if len(sys.argv) > 6 else 30

print(f"CONNECTING to {host}:{port} as {user}...", flush=True)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(
        hostname=host,
        port=port,
        username=user,
        password=password,
        timeout=15,
        banner_timeout=10,
        auth_timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    print("SSH_READY", flush=True)

    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()

    print("OUTPUT_START", flush=True)
    if out:
        print(out, flush=True)
    if err:
        print("STDERR:", err, flush=True)
    print("OUTPUT_END", flush=True)
    print(f"EXIT_CODE: {exit_code}", flush=True)

except Exception as e:
    print(f"SSH_ERROR: {e}", flush=True)
    sys.exit(1)
finally:
    client.close()
