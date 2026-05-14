import paramiko, urllib.request
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
NAME = "app_promptcfg_20260514_222647_f9f6.apk"
def run(cmd):
    c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST,username=USER,password=PWD,timeout=20,look_for_keys=False,allow_agent=False)
    _,o,e=c.exec_command(cmd,timeout=60); return o.read().decode(),e.read().decode()
cmds = [
    f"ls -la /home/ubuntu/{DEPLOY_ID}/static/{NAME}",
    f"docker exec gateway ls -la /data/static/{NAME}",
    f"docker exec gateway ls -la /data/static/app_prd440_20260510014236_5145.apk",
    # also check apk subdir
    f"ls -la /home/ubuntu/{DEPLOY_ID}/static/apk/ | tail -10",
]
for c in cmds:
    print('\n$ '+c); o,e=run(c); print(o)
    if e.strip(): print('[ERR]',e)

# fetch headers for both files
for url_path in [NAME, "app_prd440_20260510014236_5145.apk", f"apk/{NAME}"]:
    url = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/{url_path}"
    print("\n>> "+url)
    try:
        req=urllib.request.Request(url,method="HEAD")
        with urllib.request.urlopen(req,timeout=15) as r:
            print("status:", r.status)
            for k,v in r.headers.items(): print(f"  {k}: {v}")
    except Exception as e:
        print("ERR:", e)
