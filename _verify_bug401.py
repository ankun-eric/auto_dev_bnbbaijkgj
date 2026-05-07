"""验证 Bug401 修复后的页面响应"""
import paramiko, time

HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE=f"https://newbb.test.bangbangvip.com/autodev/{DID}"

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, timeout=60):
    print(f"\n>>> {cmd}")
    stdin,stdout,stderr=c.exec_command(cmd, timeout=timeout)
    out=stdout.read().decode("utf-8",errors="ignore")
    err=stderr.read().decode("utf-8",errors="ignore")
    print(out)
    if err: print("[err]",err[:500])
    return stdout.channel.recv_exit_status(), out

# 1. orders 列表页（带尾斜杠）
run(f"curl -sL -o /tmp/orders.html -w 'http=%{{http_code}} size=%{{size_download}}\\n' '{BASE}/admin/product-system/orders/'")
run(f"head -c 800 /tmp/orders.html | tr -d '\\0'")
# 关键：查找是否包含 Gateway OK
run(f"grep -c 'Gateway OK' /tmp/orders.html || echo 'Gateway OK 不存在 ✓'")
# 关键：查找是否包含 订单明细
run(f"grep -c '订单明细' /tmp/orders.html && echo 'OK: 包含订单明细标题'")
# 关键：旧"切换到预约看板"按钮应已不在
run(f"grep -c '切换到预约看板' /tmp/orders.html || echo 'OK: 旧按钮已移除'")
# 关键：旧"自动跳转 dashboard"逻辑应不在
run(f"grep -c '/orders/dashboard' /tmp/orders.html || echo 'OK: 不再含自动跳 dashboard 引用'")

# 2. dashboard 不带 storeId (应渲染友好提示页，非 Gateway OK)
run(f"curl -sL -o /tmp/dash.html -w 'http=%{{http_code}} size=%{{size_download}}\\n' '{BASE}/admin/product-system/orders/dashboard/'")
run(f"head -c 800 /tmp/dash.html")
run(f"grep -c 'Gateway OK' /tmp/dash.html || echo 'Gateway OK 不存在 ✓'")
# 需要包含友好提示文字 (服务端渲染或脚本里)
run(f"grep -c '请先选择门店' /tmp/dash.html && echo 'OK: 友好提示存在'")
run(f"grep -c '前往门店列表' /tmp/dash.html && echo 'OK: 跳转按钮存在'")

# 3. dashboard 带 storeId （正常进入）
run(f"curl -sL -o /tmp/dash2.html -w 'http=%{{http_code}} size=%{{size_download}}\\n' '{BASE}/admin/product-system/orders/dashboard/?storeId=1'")
run(f"head -c 600 /tmp/dash2.html")
run(f"grep -c 'Gateway OK' /tmp/dash2.html || echo 'Gateway OK 不存在 ✓'")

# 4. 看一下 admin 容器日志确认没运行时错误
run(f"docker logs --tail 30 {DID}-admin 2>&1")

c.close()
