"""检查 admin 容器内 seed-import 页面文件是否存在，并查看 next dev 编译日志"""
import paramiko
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

def sh(cli, cmd, t=120):
    si, so, se = cli.exec_command(cmd, timeout=t)
    return so.read().decode(errors='replace'), se.read().decode(errors='replace'), so.channel.recv_exit_status()

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=60)
try:
    # 文件是否在?
    o,_,_ = sh(cli, f"docker exec {DEPLOY_ID}-admin sh -c \"ls -la '/app/src/app/(admin)/system/seed-import/'\"")
    print("--- ls (admin)/system/seed-import/ ---")
    print(o)
    # layout.tsx 内 menu key
    o,_,_ = sh(cli, f"docker exec {DEPLOY_ID}-admin sh -c \"grep -n 'seed-import' '/app/src/app/(admin)/layout.tsx'\"")
    print("--- grep seed-import in layout.tsx ---")
    print(o)
    # admin 启动日志
    o,_,_ = sh(cli, f"docker logs --tail 100 {DEPLOY_ID}-admin 2>&1 | tail -60")
    print("--- admin logs tail ---")
    print(o)
    # 不带 admin 前缀直访问试一下
    for path in ("/admin/system/seed-import/", "/admin/system/seed-import"):
        o,_,_ = sh(cli, f"curl -s -L -o /dev/null -w '%{{http_code}}' --max-time 25 '{BASE}{path}'")
        print(f"  {path} -> {o.strip()}")
    # 直接 curl admin container 内（不通过 gateway）
    o,_,_ = sh(cli, f"docker exec {DEPLOY_ID}-admin sh -c 'curl -s -L -o /dev/null -w \"%{{http_code}}\" http://127.0.0.1:3000/admin/system/seed-import'")
    print(f"  admin 容器内 /admin/system/seed-import -> {o.strip()}")
finally:
    cli.close()
