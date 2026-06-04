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
# H5 状态
run("docker ps --filter name=6b099ed3-7175-4a78-91f4-44570c84ed27 --format \"{{.Names}}\t{{.Status}}\"")
# 等 30s 后再次健康
time.sleep(15)
run("curl -sk -o /dev/null -w \"%{http_code}\\n\" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health-profile/i-guard")
run("curl -sk -o /dev/null -w \"%{http_code}\\n\" https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/guardian/v13/family/list")
# H5 grep 含改动
run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 grep -c \"BUGFIX-MY-GUARDIAN-CARD-2\" /app/server.js 2>&1 | head -3")
run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'grep -rc \"guard-xy\" /app/.next 2>/dev/null | grep -v \":0$\" | head -5'")
ssh.close()
