import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

def run(cmd):
    print(f"$ {cmd}")
    _, o, e = c.exec_command(cmd)
    so = o.read().decode().strip(); se = e.read().decode().strip()
    if so: print(so)
    if se: print(f"[stderr] {se}")
    return so

run("docker inspect gateway --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'")
c.close()
