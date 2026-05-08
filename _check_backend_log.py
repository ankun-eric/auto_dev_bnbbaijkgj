import paramiko, sys

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
try:
    BC = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"
    _, stdout, _ = cli.exec_command(f"docker logs --tail 80 {BC} 2>&1")
    print(stdout.read().decode("utf-8", errors="replace"))
finally:
    cli.close()
