import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PWD,timeout=30,allow_agent=False,look_for_keys=False)
def run(cmd):
    si,so,se=c.exec_command(cmd); return so.read().decode(errors='replace')+se.read().decode(errors='replace')

print("=== host: /home/ubuntu/<id>/static contents ===")
print(run("ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/"))
print("=== host: /home/ubuntu/<id>/static/downloads contents ===")
print(run("ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/downloads/"))
print("=== container: ls /data/static/ (recursive shallow) ===")
print(run("docker exec gateway sh -c 'ls -la /data/static/; echo ---; ls -la /data/static/downloads/ 2>&1'"))
print("=== container mount detail ===")
print(run("docker exec gateway mount | grep /data/static"))
print("=== inode comparison ===")
print(run("stat -c '%i %n' /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/"))
print(run("docker exec gateway stat -c '%i %n' /data/static/"))

# Test access log
print("=== nginx access log tail ===")
print(run("docker exec gateway tail -20 /var/log/nginx/access.log 2>/dev/null; docker logs --tail 30 gateway 2>&1"))

# Check if path through /miniprogram/ works since that one has alias /data/static/miniprogram
print("=== Try miniprogram subpath route ===")
print(run('curl -skI "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_book_after_pay_20260503_203459_5d02.zip" | head -3'))
