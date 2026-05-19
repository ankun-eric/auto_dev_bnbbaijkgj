import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888",
          timeout=30, allow_agent=False, look_for_keys=False)
_, o, _ = c.exec_command(
    "docker logs --tail 300 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 "
    "| grep -E 'legacy_home_cleanup|prd_legacy|home_cleanup' | tail -30"
)
print(o.read().decode())
c.close()
