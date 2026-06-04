from _ssh_helper import run

def step(title, cmd, timeout=60):
    print(f"\n========== {title} ==========")
    rc, out, err = run(cmd, timeout=timeout)
    print(out)
    if err.strip():
        print("[stderr]", err[-500:])

PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
step("compose文件列表", f"ls -la {PROJ}/docker-compose*.yml")
step("admin-web服务定义", f"grep -n -A25 'admin-web:' {PROJ}/docker-compose.prod.yml")
step("compose networks段", f"grep -n -A15 '^networks:' {PROJ}/docker-compose.prod.yml")
step("admin容器的HOSTNAME环境变量", "sudo docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' 6b099ed3-7175-4a78-91f4-44570c84ed27-admin | grep -iE 'host|port|node'")
