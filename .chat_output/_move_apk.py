"""把 APK 复制到 static/apk/ 并验证 /apk/{name} 是否 200，同时保留根路径用 /downloads/ 试试。"""
import paramiko, json
HOST = "newbb.test.bangbangvip.com"; USER = "ubuntu"; PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ROOT = f"/home/ubuntu/{DEPLOY_ID}"

with open(".chat_output/_apk_final2.json", encoding="utf-8") as f:
    info = json.load(f)
apk_name = info["android"]["apk_remote_name"]

cli = paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
def run(cmd):
    print(f"$ {cmd}")
    _, o, e = cli.exec_command(cmd, timeout=60)
    out = o.read().decode("utf-8","ignore"); print(out)
    er = e.read().decode("utf-8","ignore")
    if er.strip(): print("STDERR:", er[:300])
    return out

run(f"mkdir -p {ROOT}/static/apk/")
run(f"cp -v {ROOT}/{apk_name} {ROOT}/static/apk/{apk_name}")
run(f"chmod 644 {ROOT}/static/apk/{apk_name}")
url_apk = f"https://{HOST}/autodev/{DEPLOY_ID}/apk/{apk_name}"
url_root = f"https://{HOST}/autodev/{DEPLOY_ID}/{apk_name}"
out_apk = run(f'curl -s -o /dev/null -w "%{{http_code}}" "{url_apk}"')
out_root = run(f'curl -s -o /dev/null -w "%{{http_code}}" "{url_root}"')
print(f"\n/apk/  -> {out_apk}\n/root/ -> {out_root}")
cli.close()

with open(".chat_output/_apk_final3.json","w",encoding="utf-8") as f:
    json.dump({
        "apk_url_apk_path": url_apk,
        "apk_url_root_path": url_root,
        "http_apk": out_apk,
        "http_root": out_root,
        "apk_name": apk_name,
    }, f, indent=2)
