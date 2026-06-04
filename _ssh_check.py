import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"

c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=20)
def run(cmd):
    si,so,se = c.exec_command(cmd, timeout=60)
    out = so.read().decode("utf-8", "ignore")
    err = se.read().decode("utf-8", "ignore")
    return so.channel.recv_exit_status(), out, err

# 找到容器对应的目录
for cmd in [
    f"docker inspect {DEPLOY_ID}-backend --format '{{{{.Config.Labels}}}}' 2>&1 | tr ' ' '\\n' | grep -i 'project.working_dir\\|com.docker.compose.project' || true",
    f"docker inspect {DEPLOY_ID}-backend --format '{{{{json .Mounts}}}}' 2>&1 | head -c 500",
    f"docker inspect {DEPLOY_ID}-backend --format '{{{{index .Config.Labels \"com.docker.compose.project.working_dir\"}}}}'",
]:
    code,out,err = run(cmd)
    print(f"$ {cmd}\n[code={code}]\n{out}{err}\n---")
c.close()
