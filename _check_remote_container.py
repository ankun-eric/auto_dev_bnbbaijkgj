import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
CONT = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"
for cmd in [
    f"docker exec {CONT} grep -c 'isoformat() + ' /app/app/api/home_safety_v1.py",
    f"docker exec {CONT} grep -n 'bound_at' /app/app/api/home_safety_v1.py | head -8",
    f"docker exec {CONT} ls -la /app/app/api/home_safety_v1.py",
    f"docker inspect {CONT} --format '{{{{.State.StartedAt}}}}'",
]:
    print("$", cmd)
    i, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", errors="replace"))
    er = e.read().decode("utf-8", errors="replace")
    if er.strip():
        print("[stderr]", er)
c.close()
