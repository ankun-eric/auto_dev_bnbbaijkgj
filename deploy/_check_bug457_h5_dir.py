"""[BUG-457] 在服务器上找到 H5 源码部署目录"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def run(cmd: str, timeout: int = 30) -> str:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=20)
    _, out, err = ssh.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", errors="replace")
    e = err.read().decode("utf-8", errors="replace")
    ssh.close()
    return f"STDOUT:\n{o}\nSTDERR:\n{e}"


print("=== inspect h5 container source mount ===")
print(run(
    f"docker inspect {PROJECT_ID}-h5 --format '{{{{json .Mounts}}}}' 2>&1 | head -c 2000"
))

print("\n=== inspect h5 container working dir & cmd ===")
print(run(
    f"docker inspect {PROJECT_ID}-h5 --format 'image={{{{.Config.Image}}}}\\nworkingdir={{{{.Config.WorkingDir}}}}\\ncmd={{{{.Config.Cmd}}}}\\nentrypoint={{{{.Config.Entrypoint}}}}'"
))

print("\n=== find docker-compose for project ===")
print(run(
    f"sudo find / -name 'docker-compose*.yml' 2>/dev/null | xargs grep -l '{PROJECT_ID}' 2>/dev/null | head -5"
))

print("\n=== find project working dir ===")
print(run(
    f"sudo find / -name 'h5-web' -type d 2>/dev/null | grep -i autodev | head -5; "
    f"echo ---; sudo find /home /opt /root -maxdepth 5 -name '6b099ed3*' -type d 2>/dev/null | head -5"
))
