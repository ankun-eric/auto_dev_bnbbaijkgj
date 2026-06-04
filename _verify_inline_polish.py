import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888", timeout=30)
ct = "6b099ed3-7175-4a78-91f4-44570c84ed27-h5"
cmd = (
    f"docker exec {ct} sh -lc "
    "'echo ===E0E0E0===; grep -rl E0E0E0 .next 2>/dev/null | head -5; "
        "echo ===clamp===; grep -rl '6vw' .next 2>/dev/null | head -5; "
    "echo ===STATS-INLINE chunks===; grep -rl 已绑定总数 .next 2>/dev/null | head -5'"
)
i, o, e = c.exec_command(cmd, timeout=90)
print(o.read().decode("utf-8", "replace"))
err = e.read().decode("utf-8", "replace")
if err.strip():
    print("STDERR:", err[:800])
c.close()
