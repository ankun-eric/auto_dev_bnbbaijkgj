import paramiko, time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ = f"/home/ubuntu/{DID}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, t=600, label=None):
    if label: print(f"\n===== {label} =====")
    print(f"$ {cmd}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode("utf-8","ignore")
    err = stderr.read().decode("utf-8","ignore")
    print(out)
    if err.strip(): print("[stderr]", err[-2000:])
    return out + err

# 等待后端就绪
time.sleep(8)

# 1) 容器内运行新测试（使用 sqlite 内存库，不污染 mysql）
run(f"docker exec {DID}-backend python -m pytest tests/test_home_safety_device_stats_v1_20260602.py -p no:cacheprovider -q 2>&1 | tail -15", t=600, label="pytest device stats")

# 2) 外部 HTTPS 健康检查
run("curl -s -o /dev/null -w 'health=%{http_code}\\n' https://newbb.test.bangbangvip.com/autodev/" + DID + "/api/health", label="external health")

# 3) 设备接口需要鉴权，确认其返回 401（可达）
run("curl -s -o /dev/null -w 'devices=%{http_code}\\n' https://newbb.test.bangbangvip.com/autodev/" + DID + "/api/home_safety/devices", label="external devices (expect 401/403)")

# 4) H5 居家安全页面可达性
run("curl -s -o /dev/null -w 'h5_home_safety=%{http_code}\\n' https://newbb.test.bangbangvip.com/autodev/" + DID + "/home-safety", label="external h5 page")
run("curl -s -o /dev/null -w 'h5_root=%{http_code}\\n' https://newbb.test.bangbangvip.com/autodev/" + DID + "/", label="external h5 root")

c.close()
print("\nDONE")
