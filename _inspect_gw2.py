import paramiko
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888', timeout=20, look_for_keys=False, allow_agent=False)

def r(cmd, sudo=False):
    full = cmd
    if sudo:
        full = "echo 'Newbang888' | sudo -S bash -lc \"" + cmd.replace('"', '\\"') + "\""
    _, o, e = cli.exec_command(full, timeout=60)
    print("$", cmd[:200])
    print(o.read().decode(errors='replace'))
    err = e.read().decode(errors='replace')
    if err.strip() and "sudo" not in err[:50]:
        print("[err]", err[:500])
    print("---")

r("cat /home/ubuntu/gateway/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf")
print("\n\n=== apk conf ===")
r("cat /home/ubuntu/gateway/conf.d/gateway-routes/6b099ed3-7175-4a78-91f4-44570c84ed27-apk.conf")
cli.close()
