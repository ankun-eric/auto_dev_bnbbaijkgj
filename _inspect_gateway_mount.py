import json
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("43.135.169.167", username="ubuntu", password="Newbang888", timeout=30)


def run(cmd: str) -> str:
    _, stdout, stderr = c.exec_command(cmd, timeout=90)
    return (
        stdout.read().decode("utf-8", errors="replace")
        + stderr.read().decode("utf-8", errors="replace")
    )


out = run(
    'docker inspect gateway-nginx --format "{{json .Mounts}}"'
)
print(out)
try:
    mounts = json.loads(out.strip())
    for m in mounts:
        print(m.get("Destination"), "->", m.get("Source"))
except Exception as e:
    print("parse err", e)

print("=== file inside container ===")
print(
    run(
        'docker exec gateway-nginx ls -la /usr/share/nginx/html/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/ 2>&1'
    )
)

c.close()
