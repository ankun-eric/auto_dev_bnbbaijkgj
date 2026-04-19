import paramiko
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
cmds = [
    f"docker ps --filter name={DID} --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}'",
    f"docker network inspect {DID}-network --format 'containers: {{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'",
    "docker exec gateway nginx -T 2>/dev/null | grep -E 'ssl_certificate|listen.*443.*ssl' | sort -u",
    "curl -sI https://newbb.test.bangbangvip.com/ | head -3",
]
for cmd in cmds:
    print(f"\n$ {cmd[:180]}")
    s,o,e = c.exec_command(cmd)
    print(o.read().decode())
    err = e.read().decode()
    if err:
        print(f"[stderr] {err[:200]}")
c.close()
