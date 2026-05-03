import paramiko
HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)

def run(cmd):
    print(f"$ {cmd}")
    _, o, e = cli.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", "ignore"))
    er = e.read().decode("utf-8", "ignore")
    if er.strip():
        print("STDERR:", er[:2000])

# 找 gateway-nginx 容器
run("docker ps --format '{{.Names}}' | grep -i gateway")
# 看挂载点（找到 deploy 配置）
run("docker exec gateway-nginx cat /etc/nginx/conf.d/autodev.conf 2>/dev/null | head -200")
run("docker exec gateway-nginx ls /etc/nginx/conf.d/")

# 也找一下专门给本部署的配置文件
run(f"sudo cat /home/ubuntu/{DEPLOY_ID}/nginx-conf-extra.conf 2>/dev/null || true")
run(f"ls /home/ubuntu/{DEPLOY_ID}/ | head -50")

# 查看现有部署如何处理 /miniprogram/  /apk/ 之类
run("docker exec gateway-nginx grep -rn 'miniprogram\\|apk\\|" + DEPLOY_ID[:12] + "' /etc/nginx/ 2>/dev/null | head -30")
cli.close()
