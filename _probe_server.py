import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("43.135.169.167", username="ubuntu", password="Newbang888", timeout=30)


def run(cmd: str) -> str:
    _, stdout, stderr = c.exec_command(cmd, timeout=90)
    o = stdout.read().decode("utf-8", errors="replace")
    e = stderr.read().decode("utf-8", errors="replace")
    return o + e


print("=== ls /home/ubuntu/autodev ===")
print(run("ls -la /home/ubuntu/autodev"))

print("=== find 3b7b ===")
print(run("find /home/ubuntu -maxdepth 5 -type d -name '*3b7b*' 2>/dev/null"))

print("=== gateway conf grep ===")
print(
    run(
        'docker exec gateway-nginx sh -c "grep -r 3b7b /etc/nginx 2>/dev/null | head -30"'
    )
)
print(
    run(
        'docker exec gateway-nginx sh -c "grep -r autodev /etc/nginx/conf.d 2>/dev/null | head -40"'
    )
)

c.close()
