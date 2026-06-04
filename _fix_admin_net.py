from _ssh_helper import run

PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

def step(title, cmd, timeout=600):
    print(f"\n========== {title} ==========", flush=True)
    rc, out, err = run(cmd, timeout=timeout)
    print(out)
    if err.strip():
        print("[stderr]", err[-1200:])
    return out

# 用 prod compose 以正确网络重建并拉起 admin-web（force-recreate 确保脱离脏网络）
step("重建并重拉admin-web(prod compose)",
     f"cd {PROJ} && sudo docker compose -f docker-compose.prod.yml up -d --build --force-recreate admin-web 2>&1 | tail -40",
     timeout=900)

step("admin容器状态", "sudo docker ps --filter name=6b099ed3 --format '{{.Names}} | {{.Status}}'")
step("admin网络列表(应只剩正确network)",
     "sudo docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}={{$v.IPAddress}} {{end}}' 6b099ed3-7175-4a78-91f4-44570c84ed27-admin")
step("admin监听端口(应为0.0.0.0:3000)",
     "sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-admin sh -c 'netstat -tlnp 2>/dev/null | grep 3000 || ss -tlnp | grep 3000'")
