import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

cmds = [
    f"cd {PROJ} && git log -1 --oneline",
    f"cd {PROJ} && grep -n nulls_last backend/app/api/function_button.py || echo NO_MATCH",
    f"cd {PROJ} && grep -n coalesce backend/app/api/function_button.py | head -5",
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend grep -c nulls_last /app/app/api/function_button.py || echo CONTAINER_NO_MATCH",
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend grep -c coalesce /app/app/api/function_button.py",
]
for cmd in cmds:
    print(f"\n>>> {cmd}")
    _, out, err = c.exec_command(cmd)
    print(out.read().decode("utf-8", errors="replace"))
c.close()
