import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

cmds = [
    f"cd {PROJ} && git remote -v",
    f"cd {PROJ} && git fetch origin 2>&1 | head -10",
    f"cd {PROJ} && git log origin/master -3 --oneline",
    f"cd {PROJ} && git reset --hard origin/master 2>&1",
    f"cd {PROJ} && git log -1 --oneline",
    f"cd {PROJ} && grep -c coalesce backend/app/api/function_button.py",
]
for cmd in cmds:
    print(f"\n>>> {cmd}")
    _, out, err = c.exec_command(cmd, timeout=60)
    print(out.read().decode("utf-8", errors="replace"))
    e = err.read().decode("utf-8", errors="replace")
    if e and not all(x in e for x in ("warning",)):
        print("ERR:", e[:400])
c.close()
