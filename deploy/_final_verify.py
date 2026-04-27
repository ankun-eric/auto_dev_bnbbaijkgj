"""Final verification of all services."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

print("=" * 60)
print("CONTAINER STATUS")
print("=" * 60)
stdin, stdout, stderr = ssh.exec_command(
    "cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && docker compose -f docker-compose.prod.yml ps 2>&1",
    timeout=30,
)
print(stdout.read().decode("utf-8", errors="replace"))

print("=" * 60)
print("LINK VERIFICATION")
print("=" * 60)
urls = {
    "H5 Frontend": "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/",
    "Admin Frontend": "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/",
    "API Docs": "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/api/docs",
}

all_ok = True
for name, url in urls.items():
    stdin, stdout, stderr = ssh.exec_command(
        f"curl -sL -o /dev/null -w '%{{http_code}}' --max-time 30 '{url}'", timeout=60
    )
    status = stdout.read().decode("utf-8", errors="replace").strip().replace("'", "")
    ok = status in ("200", "301", "302", "307")
    print(f"  {'OK' if ok else 'FAIL'} | {name}: {url} -> HTTP {status}")
    if not ok:
        all_ok = False

print()
if all_ok:
    print("ALL LINKS ARE REACHABLE!")
else:
    print("SOME LINKS FAILED!")

ssh.close()
