import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PWD,timeout=30,allow_agent=False,look_for_keys=False)
def run(cmd):
    si,so,se=c.exec_command(cmd); return so.read().decode(errors='replace')+se.read().decode(errors='replace')

# What does nginx container see at /data/static/downloads?
print("=== container view of /data/static ===")
print(run("docker exec gateway ls -la /data/static/ 2>&1"))
print("=== container view of /data/static/downloads ===")
print(run("docker exec gateway ls -la /data/static/downloads/ 2>&1 | head -20"))
print("=== check existing zip working URL ===")
# the uploaded file from before -- /data/static/downloads/miniprogram_book_after_pay_20260503_203459_5d02.zip
# was placed by sudo to /data/static/downloads on host - that's a different host path
print(run("docker exec gateway cat /etc/nginx/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf 2>&1 | grep -A5 'AUTO: direct zip'"))
print("=== try a known working zip URL ===")
print(run('curl -skI "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram_20260420_010639_4618.zip" | head -3'))
print("=== try URL via /miniprogram/ path (the dedicated location) ===")
print(run('curl -skI "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260420_010639_4618.zip" | head -3'))
# Find what path 'miniprogram_20260430_132720_9AC8.zip' served - it's accessible somewhere
print("=== where is 9AC8 reachable ===")
for url in [
    "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram_20260430_132720_9AC8.zip",
    "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_20260430_132720_9AC8.zip",
    "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/static/downloads/miniprogram_20260430_132720_9AC8.zip",
    "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_20260430_132720_9AC8.zip",
]:
    print(url)
    print(run(f'curl -skI "{url}" | head -3'))
