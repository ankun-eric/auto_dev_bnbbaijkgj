import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
def run(cmd):
    stdin,stdout,stderr=ssh.exec_command(cmd, timeout=60)
    code=stdout.channel.recv_exit_status()
    out=stdout.read().decode("utf-8",errors="replace")
    err=stderr.read().decode("utf-8",errors="replace")
    print(f"$ {cmd[:200]}\n  exit={code}\n  out={out[-400:]}\n  err={err[-400:]}\n")
run("docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27_6b099ed3-7175-4a78-91f4-44570c84ed27-network gateway 2>&1 || true")
run("docker exec gateway nginx -t && docker exec gateway nginx -s reload")
import time; time.sleep(5)
for u in ["https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/", "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/", "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/docs"]:
    run(f"curl -skI \"{u}\" | head -3")
ssh.close()
