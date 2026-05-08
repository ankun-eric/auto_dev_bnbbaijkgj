import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=30)


def run(cmd, t=900):
    print(f"\n>>> {cmd[:120]}")
    s, o, e = ssh.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if out:
        print(out[-3000:])
    if err:
        print("STDERR:", err[-500:])
    print(f"<<< exit={o.channel.recv_exit_status()}")


run('docker builder prune -af', 900)
run('docker image prune -af --filter until=72h', 600)
run('df -h /')
ssh.close()
print("done")
