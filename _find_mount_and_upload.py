import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"

ZIP_NAME = "miniprogram_20260601_234926_7f1c.zip"
LOCAL_ZIP = r"C:\auto_output\bnbbaijkgj\\" + ZIP_NAME
CONTAINER_DIR = "/data/static/apk/"

def run(cli, cmd, timeout=60):
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, PORT, USER, PWD, timeout=30)

# Inspect the mount for /data/static in gateway-nginx
out, err = run(cli, "docker inspect gateway-nginx --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}\\n{{end}}'")
print("### MOUNTS gateway-nginx")
print(out)
if err.strip():
    print("ERR:", err)

# list existing apk dir contents inside container (confirm existing mp zips)
out, _ = run(cli, "docker exec gateway-nginx ls -la /data/static/apk/ | tail -n 20")
print("### container /data/static/apk/ (tail)")
print(out)

cli.close()
