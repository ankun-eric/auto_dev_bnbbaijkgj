import _ssh_helper as sh

with open("_mp_zip_name.txt") as f:
    NAME = f.read().strip()
LOCAL = rf"C:\auto_output\bnbbaijkgj\{NAME}"
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"
BE = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"
HOST_TMP = f"{PROJ}/_deploy_tmp/{NAME}"

sh.run(f"mkdir -p {PROJ}/_deploy_tmp")
sh.put_file(LOCAL, HOST_TMP)
print("uploaded to host:", HOST_TMP)
rc, o, e = sh.run(f'docker cp "{HOST_TMP}" {BE}:/app/uploads/{NAME}')
print("docker cp rc", rc, e.strip()[:200])
rc, o, e = sh.run(f"docker exec {BE} ls -la /app/uploads/{NAME}")
print(o.strip(), e.strip())
print("NAME=", NAME)
