import paramiko, os

HOST="newbb.test.bangbangvip.com"; PORT=22; USER="ubuntu"; PWD="Newbang888"
ZIP_NAME="miniprogram_20260601_234926_7f1c.zip"
HOST_TMP="/home/ubuntu/"+ZIP_NAME
CONTAINER_PATH="/data/static/apk/"+ZIP_NAME

def run(cli,cmd,timeout=120):
    i,o,e=cli.exec_command(cmd,timeout=timeout)
    return o.read().decode("utf-8","ignore"), e.read().decode("utf-8","ignore")

cli=paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,PORT,USER,PWD,timeout=30)

# We already uploaded to static/miniprogram; copy that file to home tmp then docker cp.
SRC_ON_HOST="/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/miniprogram/"+ZIP_NAME
out,err=run(cli, f"cp '{SRC_ON_HOST}' '{HOST_TMP}' && docker cp '{HOST_TMP}' gateway-nginx:'{CONTAINER_PATH}' && docker exec gateway-nginx ls -la '{CONTAINER_PATH}' && rm -f '{HOST_TMP}'")
print("OUT:", out)
print("ERR:", err)
cli.close()
