import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com',username='ubuntu',password='Newbang888',timeout=30,allow_agent=False,look_for_keys=False)
_,o,_=c.exec_command('docker logs --tail 1500 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | grep -E "home_grid|prd_aichat_home" 2>&1 | head -50')
print("---SEARCH 1---")
print(o.read().decode("utf-8", errors="replace"))

_,o2,_=c.exec_command('docker logs --tail 1500 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | grep -i "migrate" | head -80')
print("---SEARCH 2 migrate---")
print(o2.read().decode("utf-8", errors="replace"))
c.close()
