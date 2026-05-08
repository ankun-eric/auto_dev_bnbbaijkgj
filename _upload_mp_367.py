import paramiko, sys, os

LOCAL = sys.argv[1]
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
remote_dir = f"/home/ubuntu/{DEPLOY_ID}/static/miniprogram"
remote = f"{remote_dir}/{os.path.basename(LOCAL)}"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
try:
    cli.exec_command(f"mkdir -p {remote_dir}")
    sftp = cli.open_sftp()
    sftp.put(LOCAL, remote)
    sftp.close()
    print(f"[ok] uploaded -> {remote}")
    print(f"URL: https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/miniprogram/{os.path.basename(LOCAL)}")
finally:
    cli.close()
