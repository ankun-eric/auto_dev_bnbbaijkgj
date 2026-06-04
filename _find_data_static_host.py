import paramiko

HOST = "newbb.test.bangbangvip.com"; PORT=22; USER="ubuntu"; PWD="Newbang888"

def run(cli, cmd, timeout=60):
    i,o,e = cli.exec_command(cmd, timeout=timeout)
    return o.read().decode("utf-8","ignore"), e.read().decode("utf-8","ignore")

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,PORT,USER,PWD,timeout=30)

# full mount inspection incl volumes
out,err = run(cli, "docker inspect gateway-nginx --format '{{json .Mounts}}'")
print("### Mounts json"); print(out)

# Is /data/static a mount inside container? check mountinfo
out,_ = run(cli, "docker exec gateway-nginx cat /proc/mounts | grep -i /data || echo NO_DATA_MOUNT")
print("### proc mounts /data"); print(out)

# Try to locate the file on host directly
out,_ = run(cli, "find /home/ubuntu -maxdepth 5 -name 'miniprogram_20260601_232958_35ff.zip' 2>/dev/null; find /data -maxdepth 5 -name 'miniprogram_20260601_232958_35ff.zip' 2>/dev/null; echo DONE")
print("### host find existing zip"); print(out)

cli.close()
