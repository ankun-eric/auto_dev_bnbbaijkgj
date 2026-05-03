import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,username=USER,password=PWD,timeout=30,allow_agent=False,look_for_keys=False)
def run(cmd):
    si,so,se=c.exec_command(cmd); return so.read().decode(errors='replace')+se.read().decode(errors='replace')

print("=== container /data/cli-static ===")
print(run("docker exec gateway ls -la /data/cli-static/ 2>&1 | head -10"))
print("=== container /data tree ===")
print(run("docker exec gateway find /data -maxdepth 3 -type f 2>/dev/null | head -30"))
print("=== container all mounts ===")
print(run("docker exec gateway mount | grep -v -E 'cgroup|proc|sys|tmp'"))
print("=== container view of conf.d location related vol ===")
print(run("docker exec gateway sh -c 'ls -la /etc/nginx/conf.d/ | head'"))
print("=== check what's at container's /data/static via -L ===")
print(run("docker exec gateway sh -c 'readlink -f /data/static; mount | head'"))
# Check if there's a path inside the container that points to /data/static folder when freshly set up
print("=== inspect: bind source verify ===")
print(run("docker inspect gateway --format '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}|{{.Mode}}{{println}}{{end}}'"))
