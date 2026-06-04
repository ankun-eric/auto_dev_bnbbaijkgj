import paramiko, time
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
def run(cmd, timeout=300):
    print(f">>> {cmd[:160]}")
    _, so, se = ssh.exec_command(cmd, timeout=timeout)
    o = so.read().decode("utf-8", errors="replace"); e = se.read().decode("utf-8", errors="replace")
    if o: print(o[-2000:])
    if e: print("STDERR:", e[-800:])
    print(f"[exit={so.channel.recv_exit_status()}]")
    return o
# 检查 gateway 是否能访问 backend 和 h5
run("docker logs --tail 10 gateway-nginx 2>&1 || docker ps | grep gateway")
run("docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --format '{{json .NetworkSettings.Networks}}' | head -c 500")
run("docker inspect 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 --format '{{json .NetworkSettings.Networks}}' | head -c 500")
# 跟踪重定向
run("curl -skL -o /dev/null -w \"%{http_code} -> %{url_effective}\\n\" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health-profile/i-guard")
# 直接到容器
run("curl -s -o /dev/null -w \"%{http_code}\\n\" http://6b099ed3-7175-4a78-91f4-44570c84ed27-h5:3000//health-profile/i-guard")
ssh.close()
