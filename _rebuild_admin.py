from _ssh_helper import run
print("=== Rebuild admin-web ===")
rc, out, err = run(
    "cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 && "
    "sudo docker compose -f docker-compose.prod.yml up -d --build admin-web 2>&1 | tail -30",
    timeout=600,
)
print(out)
print("---ERR---", err[-1000:] if err else "")

print("\n=== Container status ===")
rc, out, err = run("sudo docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}'", timeout=30)
print(out)

print("\n=== Smoke admin page ===")
rc, out, err = run(
    "curl -sk -o /dev/null -w 'HTTP %{http_code}\\n' "
    "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/home-safety",
    timeout=30,
)
print(out)
