"""检查 gateway nginx 中本项目的 location 配置"""
import paramiko

SSH_HOST = "newbb.test.bangbangvip.com"
SSH_USER = "ubuntu"
SSH_PASS = "Newbang888"

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=30)
    cmds = [
        "docker exec gateway cat /etc/nginx/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf",
    ]
    for cmd in cmds:
        print(f"\n>>> {cmd}")
        _, out, err = c.exec_command(cmd)
        print(out.read().decode("utf-8", errors="replace"))
        e = err.read().decode("utf-8", errors="replace")
        if e.strip():
            print("ERR:", e)
    c.close()

if __name__ == "__main__":
    main()
