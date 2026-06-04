import paramiko
import sys

def run_ssh(host, port, username, password, command, timeout=30):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=username, password=password, timeout=15)
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    exit_code = stdout.channel.recv_exit_status()
    client.close()
    return out, err, exit_code

if __name__ == "__main__":
    print("=== ACR 连通性验证 ===")
    print("在测试环境服务器上执行 docker login...")

    out, err, code = run_ssh(
        "newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888",
        "docker login --username=ankun888 --password=xiaobai888 crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com",
        timeout=30
    )

    print(f"stdout: {out}")
    print(f"stderr: {err}")
    print(f"exit_code: {code}")

    if code == 0 and "Login Succeeded" in out:
        print("\nACR 登录验证成功！")
        sys.exit(0)
    else:
        print("\nACR 登录验证失败！")
        sys.exit(1)
