"""测试 h5 容器健康与路径返回情况"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"

CMDS = [
    f"docker ps --format '{{{{.Names}}}} {{{{.Status}}}}' | grep {TOKEN}",
    # 从 gateway 内部直接访问 H5 容器
    f"docker exec gateway sh -c 'curl -s -o /dev/null -w \"%{{http_code}}\\n\" http://{TOKEN}-h5:3001/'",
    f"docker exec gateway sh -c 'curl -s -o /dev/null -w \"%{{http_code}}\\n\" http://{TOKEN}-h5:3001/autodev/{TOKEN}/health-profile/i-guard'",
    f"docker exec gateway sh -c 'curl -s -o /dev/null -w \"%{{http_code}}\\n\" http://{TOKEN}-h5:3001/autodev/{TOKEN}/'",
    # 通过 host 80 / 443 测试
    f"curl -s -o /dev/null -w 'host80=%{{http_code}}\\n' http://127.0.0.1/autodev/{TOKEN}/",
    f"curl -k -s -o /dev/null -w 'host443=%{{http_code}}\\n' https://127.0.0.1/autodev/{TOKEN}/health-profile/i-guard",
    f"curl -k -s -o /dev/null -w 'domain443=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{TOKEN}/health-profile/i-guard",
    f"curl -k -s -L -o /dev/null -w 'domain443L=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{TOKEN}/health-profile/i-guard",
    # H5 容器日志
    f"docker logs --tail 30 {TOKEN}-h5 2>&1",
    # 看 gateway 网络成员（确认新容器在网络中）
    f"docker network inspect {TOKEN}-network --format '{{{{range .Containers}}}}{{{{.Name}}}}|{{{{end}}}}'",
]


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    for c in CMDS:
        print("\n==== CMD:", c[:180])
        si, so, se = cli.exec_command(c, timeout=30)
        out = so.read().decode("utf-8", errors="ignore")
        err = se.read().decode("utf-8", errors="ignore")
        if out.strip():
            print(out)
        if err.strip():
            print("--stderr--")
            print(err)
    cli.close()


if __name__ == "__main__":
    main()
