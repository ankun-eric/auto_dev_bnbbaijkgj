import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
_, out, err = c.exec_command(
    "cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml logs --tail=200 backend | tail -120"
)
print(out.read().decode("utf-8", errors="replace"))
c.close()
