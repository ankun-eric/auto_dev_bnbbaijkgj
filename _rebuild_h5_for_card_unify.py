"""[PRD-HEALTH-METRIC-CARD-UNIFY-V1] H5 重新构建。"""
import paramiko, time

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
PROJECT = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

def run(cmd, timeout=600):
    print(f"\n$ {cmd[:120]}")
    chan = cli.get_transport().open_session()
    chan.set_combine_stderr(True)
    chan.exec_command(cmd)
    out = b""
    while True:
        if chan.recv_ready():
            data = chan.recv(8192)
            if not data: break
            out += data
            try: print(data.decode('utf-8', 'replace'), end='', flush=True)
            except Exception: pass
        if chan.exit_status_ready():
            # drain
            while chan.recv_ready():
                data = chan.recv(8192)
                out += data
                try: print(data.decode('utf-8', 'replace'), end='', flush=True)
                except Exception: pass
            break
        time.sleep(0.5)
    return chan.recv_exit_status(), out.decode('utf-8', 'replace')


# 重新构建 h5 镜像并重启容器
code, _ = run(f"cd {PROJECT} && docker compose build h5-web 2>&1 | tail -50", timeout=900)
if code == 0:
    print("\n[build OK]")
    run(f"cd {PROJECT} && docker compose up -d h5-web 2>&1 | tail -10", timeout=120)
    time.sleep(8)
    code, out = run("curl -sS -o /dev/null -w 'HTTP:%{http_code}\\n' https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health-metric/blood_pressure/history?profileId=1", timeout=30)
    print("\n[verify]", out)
else:
    print(f"\n[build FAILED] code={code}")
cli.close()
