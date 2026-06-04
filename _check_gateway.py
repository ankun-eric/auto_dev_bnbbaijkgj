import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

def run(cmd):
    print(f"$ {cmd}")
    _, o, e = c.exec_command(cmd)
    so = o.read().decode().strip(); se = e.read().decode().strip()
    if so: print(so)
    if se: print(f"[stderr] {se}")

# 看 gateway 容器名 + 挂载
run("docker ps --format '{{.Names}}' | grep -i gateway")
run("docker inspect gateway-nginx --format '{{json .Mounts}}' 2>/dev/null | python3 -m json.tool 2>&1 | head -40 || docker inspect $(docker ps --format '{{.Names}}' | grep -i gateway | head -1) --format '{{json .Mounts}}' | python3 -m json.tool 2>&1 | head -40")

# 看 gateway 容器内部能否看到该文件
run("docker exec $(docker ps --format '{{.Names}}' | grep -i gateway | head -1) ls -la /data/static/miniprogram/ 2>&1 | head -10")

c.close()
