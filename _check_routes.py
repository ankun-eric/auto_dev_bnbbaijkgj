import paramiko, time
time.sleep(2)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
cmd = (
    "docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend "
    "python -c \"from app.main import app; "
    "import json; "
    "print(json.dumps([r.path for r in app.routes if 'home_safety' in str(getattr(r,'path',''))], ensure_ascii=False))\""
)
print("$", cmd)
_, o, e = c.exec_command(cmd, timeout=30)
print(o.read().decode("utf-8", errors="replace"))
err = e.read().decode("utf-8", errors="replace")
if err.strip():
    print("[err]", err)
c.close()
