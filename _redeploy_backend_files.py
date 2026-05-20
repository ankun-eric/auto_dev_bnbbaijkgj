"""Quick backend redeploy: docker cp 文件进容器 + 重启容器，无需重建镜像"""
import paramiko
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
UUID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{UUID}"
CONT = f"{UUID}-backend"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)


def run(cmd: str, timeout: int = 300):
    print(f">>> {cmd[:200]}")
    i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    code = o.channel.recv_exit_status()
    if out:
        print(out[-2000:])
    if err:
        print("STDERR:", err[-1500:])
    print(f"[exit={code}]")
    return code, out, err


FILES = [
    "backend/app/models/models.py",
    "backend/app/api/product_admin.py",
    "backend/app/api/products.py",
    "backend/app/api/tag_recommend.py",
    "backend/app/schemas/products.py",
    "backend/app/schemas/tag_recommend.py",
    "backend/app/services/prd_tag_recommend_v1_migration.py",
]

for rel in FILES:
    # 例如 backend/app/api/tag_recommend.py → 容器内 /app/app/api/tag_recommend.py
    parts = rel.split("/", 1)  # ["backend", "app/api/tag_recommend.py"]
    in_container = f"/app/{parts[1]}"
    src = f"{PROJ}/{rel}"
    run(f"docker cp '{src}' '{CONT}:{in_container}'")

print("\n--- restart backend ---")
run(f"docker restart {CONT}", timeout=60)
time.sleep(10)
print("\n--- check logs ---")
run(f"docker logs --tail 80 {CONT} 2>&1 | grep -E 'tag_recommend|symptom|tag_columns|constitution|migrate|complete' | tail -30")

ssh.close()
print("DONE")
