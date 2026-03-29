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


print("=== nginx miniprogram zip block ===")
print(
    run(
        'docker exec gateway-nginx sh -c "grep -A8 miniprogram_ /etc/nginx/nginx.conf"'
    )
)

print("=== static dir listing ===")
print(run("ls -la /home/ubuntu/gateway/static/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/"))

ZIP = "miniprogram_20260329_122617_9985.zip"
src = f"/home/ubuntu/autodev/{ZIP}"
dst_dir = "/home/ubuntu/gateway/static/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
dst = f"{dst_dir}/{ZIP}"

print(f"=== mv {src} -> {dst} ===")
print(run(f"mv -f {src} {dst} && ls -la {dst}"))

c.close()
