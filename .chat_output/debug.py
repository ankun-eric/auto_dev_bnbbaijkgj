import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30, allow_agent=False, look_for_keys=False)

def run(cmd):
    si, so, se = c.exec_command(cmd)
    return so.read().decode(errors="replace"), se.read().decode(errors="replace"), so.channel.recv_exit_status()

# Check the file
o, e, rc = run(f"echo 'Newbang888' | sudo -S ls -la /data/static/downloads/ | tail -10")
print("ls /data/static/downloads:\n" + o)

# Check gateway nginx container & how it sees this path
o, e, rc = run("docker ps --format '{{.Names}}' | grep -i gateway")
print("gateway container:\n" + o)

o, e, rc = run("docker ps --format '{{.Names}}\t{{.Image}}' | head -20")
print("all containers:\n" + o)

# Check if /data/static is mounted into gateway container
o, e, rc = run("docker inspect $(docker ps --format '{{.Names}}' | grep -i gateway | head -1) --format '{{json .Mounts}}' 2>/dev/null")
print("gateway mounts:\n" + o)
