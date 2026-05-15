import paramiko
c=paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com',username='ubuntu',password='Newbang888',timeout=30,allow_agent=False,look_for_keys=False)
_,o,_=c.exec_command('docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -Dbini_health -e "DESCRIBE app_settings" 2>&1; docker logs --tail 1000 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | grep -E "home_grid|migrate" | tail -20')
print(o.read().decode("utf-8", errors="replace"))
c.close()
