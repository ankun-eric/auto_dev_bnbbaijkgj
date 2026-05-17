import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', 22, 'ubuntu', 'Newbang888',
          look_for_keys=False, allow_agent=False)
DD = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
cmds = [
    f"cd {DD} && git log -1 --oneline",
    f"cd {DD} && git log --oneline | head -3",
    f"cd {DD} && ls backend/tests | grep -i actionbar",
    f"cd {DD} && ls backend/tests | grep 20260517",
    f"cd {DD} && cat backend/tests/test_ai_home_actionbar_and_attachment_filter_20260517.py 2>&1 | head -3",
    f"cd {DD} && find . -name 'test_ai_home_actionbar*' 2>/dev/null",
    f"docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend find /app -name 'test_ai_home_actionbar*' 2>&1",
]
for cmd in cmds:
    _, o, e = c.exec_command(cmd)
    print(f"\n$ {cmd}")
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err)
c.close()
