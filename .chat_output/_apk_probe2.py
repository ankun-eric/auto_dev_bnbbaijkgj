"""Find where the miniprogram zip is being served from inside h5 container."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
UUID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(cmd: str) -> str:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out[:3000])
    if err:
        print("[stderr]", err[:500])
    return out


run(f"docker exec {UUID}-h5 sh -c 'ls -la /app/public/ 2>/dev/null; echo ---; ls /app/public/ | head -40'")
run(f"docker exec {UUID}-h5 sh -c 'find /app -maxdepth 3 -name \"miniprogram_*.zip\" 2>/dev/null'")
run(f"docker exec {UUID}-h5 sh -c 'find / -name \"miniprogram_20260503_212049_9128.zip\" 2>/dev/null | head -5'")
run(f"docker inspect {UUID}-h5 --format '{{{{json .Mounts}}}}' | python3 -m json.tool 2>/dev/null || docker inspect {UUID}-h5 --format '{{{{json .Mounts}}}}'")

ssh.close()
