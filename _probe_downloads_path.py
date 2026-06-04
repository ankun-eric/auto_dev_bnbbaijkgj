import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"

def run(cli, cmd, timeout=60):
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, PORT, USER, PWD, timeout=30)

cmds = [
    "docker ps --format '{{.Names}}' | grep -i gateway",
    "docker ps --format '{{.Names}}\\t{{.Image}}' | grep -i nginx",
]
for c in cmds:
    out, err = run(cli, c)
    print("### CMD:", c)
    print(out)
    if err.strip():
        print("ERR:", err)
    print("-"*40)

# find gateway container name
out, _ = run(cli, "docker ps --format '{{.Names}}' | grep -i gateway")
gw = out.strip().splitlines()
print("GATEWAY_CONTAINERS:", gw)

if gw:
    name = gw[0]
    out, err = run(cli, f"docker exec {name} nginx -T 2>/dev/null | grep -i -A5 downloads")
    print("### nginx downloads config in", name)
    print(out)
    if err.strip():
        print("ERR:", err)

cli.close()
