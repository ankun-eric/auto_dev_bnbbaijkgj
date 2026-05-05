import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888", timeout=30)

cmds = [
    "docker ps --format '{{.Names}}'",
    "ls /home/ubuntu/gateway-nginx/conf.d/ 2>/dev/null || ls /home/ubuntu/*nginx*/ 2>/dev/null",
    "find /home/ubuntu -maxdepth 4 -name 'nginx*.conf' 2>/dev/null | head -5",
    "find /home/ubuntu -maxdepth 4 -name '*.conf' -path '*nginx*' 2>/dev/null | head -10",
    "grep -rln '6b099ed3' /home/ubuntu/*nginx* /home/ubuntu/*gateway* 2>/dev/null | head -5",
]
for c in cmds:
    print(f"\n>>> {c}")
    i, o, e = ssh.exec_command(c)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err[:500])
ssh.close()
