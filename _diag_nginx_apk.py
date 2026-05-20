import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu",
          password="Newbang888", timeout=20, look_for_keys=False, allow_agent=False)


def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=30)
    out = o.read().decode("utf-8", "ignore")
    err = e.read().decode("utf-8", "ignore")
    print(f"$ {cmd}")
    print(out)
    if err.strip():
        print("[STDERR]", err)
    print("---")


run("docker exec gateway ls /data/static/apk/ 2>/dev/null")
run("ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/apk/ 2>/dev/null")
run("ls /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/")
c.close()
