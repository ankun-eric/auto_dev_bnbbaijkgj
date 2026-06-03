import paramiko, time, urllib.request, ssl

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
P=f"/home/{USER}/{DID}"
BASE=f"https://{HOST}/autodev/{DID}"

def run(cli,cmd,t=600):
    i,o,e=cli.exec_command(cmd,timeout=t)
    out=o.read().decode('utf-8','ignore'); err=e.read().decode('utf-8','ignore')
    code=o.channel.recv_exit_status()
    return code,out,err

cli=paramiko.SSHClient(); cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST,username=USER,password=PWD,timeout=30)

# 1) H5 容器内查产物是否含箭头 testid（确认新代码已上线）
code,out,err=run(cli, f"docker exec {DID}-h5 sh -c \"grep -rl 'ai-home-scroll-hint' /app/.next 2>/dev/null | head -3\" 2>&1")
print("[h5 build contains ai-home-scroll-hint?]\n", out.strip() or "(none)", err.strip())

# 2) 在 backend 容器内跑新测试（把最新测试文件拷进容器）
run(cli, f"docker cp {P}/backend/tests/test_aihome_scroll_hint_20260602.py {DID}-backend:/app/tests/test_aihome_scroll_hint_20260602.py 2>&1")
# 同时需要源码文件在容器可读？测试读的是项目根 h5-web/miniprogram，容器内 /app 是 backend。需把源码也放进去。
# 测试用 _ROOT = backend/.. = /app/.. ，容器内 /app 上一级没有 h5-web。改为在服务器宿主机直接跑 pytest。
code,out,err=run(cli, f"cd {P}/backend && python3 -m pytest tests/test_aihome_scroll_hint_20260602.py --noconftest -q 2>&1 | tail -20")
print("[host pytest]\n", out)

cli.close()

# 3) 外部 HTTPS 冒烟
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
def http(url):
    try:
        req=urllib.request.Request(url, headers={'User-Agent':'smoke'})
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return f"ERR {e}"

for path in ["/", "/ai-home", "/ai-home/", "/api/health"]:
    print(f"[HTTP] {path} -> {http(BASE+path)}")
print("VERIFY_DONE")
