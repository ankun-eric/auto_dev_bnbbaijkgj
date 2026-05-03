import paramiko
HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)

def run(cmd):
    print(f"$ {cmd}")
    _, o, e = cli.exec_command(cmd, timeout=60)
    out = o.read().decode("utf-8", "ignore")
    print(out)
    er = e.read().decode("utf-8", "ignore")
    if er.strip():
        print("STDERR:", er[:1000])
    return out

run("docker exec gateway ls /etc/nginx/conf.d/")
run(f"docker exec gateway grep -lrn '{DEPLOY_ID}' /etc/nginx/ 2>/dev/null")
# 看现存的 apk 目录在 nginx 的什么 location 下
run(f"sudo cat /home/ubuntu/gateway-nginx/conf.d/autodev_{DEPLOY_ID}.conf 2>/dev/null | head -120")
run(f"ls /home/ubuntu/gateway-nginx/conf.d/ 2>/dev/null | head -10")
run(f"find /home/ubuntu/gateway-nginx -name '*.conf' 2>/dev/null | head -10")
# 不行就看 docker compose volume
run("docker inspect gateway --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}\\n{{end}}'")
cli.close()
