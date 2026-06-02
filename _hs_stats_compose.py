import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, t=120):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    return stdout.read().decode("utf-8","ignore") + stderr.read().decode("utf-8","ignore")

print("===== docker-compose.prod.yml =====")
print(run(f"cat /home/ubuntu/{DID}/docker-compose.prod.yml"))
print("===== git status (short) =====")
print(run(f"cd /home/ubuntu/{DID} && git status --short 2>&1 | head -30"))
print("===== git branch =====")
print(run(f"cd /home/ubuntu/{DID} && git rev-parse --abbrev-ref HEAD 2>&1"))
c.close()
