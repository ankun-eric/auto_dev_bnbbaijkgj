import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com',username='ubuntu',password='Newbang888',timeout=30)
i,o,e=c.exec_command("sed -n '55,80p' /etc/nginx/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf")
print(o.read().decode('utf-8','ignore'))
# 看 backend 容器内 /downloads 对应物理路径
i,o,e=c.exec_command("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend sh -c 'ls -la /app/downloads 2>/dev/null | tail -8; echo ---; ls /app/static/downloads 2>/dev/null | tail -5'")
print("BACKEND DOWNLOADS:\n", o.read().decode('utf-8','ignore'), e.read().decode('utf-8','ignore'))
c.close()
