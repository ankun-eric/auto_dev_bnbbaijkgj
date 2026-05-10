"""PRD-442 部署 v2：重启 h5 容器让 next-server 重读 public 目录"""
import paramiko, sys, time, urllib.request, urllib.error

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(f"\n$ {cmd[:100]}")
    print(f"[rc={rc}]")
    if out: print(out[:1500])
    if err: print("ERR:", err[:500])
    return rc, out, err

# 重启 h5 容器
print("=" * 60)
print("重启 h5 容器以让 next-server 重新扫描 public/")
print("=" * 60)
run(f"docker restart {DEPLOY_ID}-h5")

# 等待启动
print("\n等待 30s 让 next-server 启动...")
time.sleep(30)

# 验证容器内文件还在（restart 不会丢失 docker cp 的文件，因为 ownership 通过镜像层持久化）
run(f"docker exec {DEPLOY_ID}-h5 ls -la /app/public/menu-mode-design-system/ 2>&1 | head -10")

# Smoke test
print("\n" + "=" * 60)
print("Smoke Test (重启后)")
print("=" * 60)

paths = [
    "/menu-mode-design-system/index.html",
    "/menu-mode-design-system/prototype.html",
    "/menu-mode-design-system/components.html",
    "/menu-mode-design-system/design-tokens.css",
    "/menu-mode-design-system/design-tokens.json",
    "/menu-mode-design-system/PRD-442.md",
]
pass_count = 0
for p in paths:
    url = BASE_URL + p
    for retry in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "smoke/1.0"})
            r = urllib.request.urlopen(req, timeout=15)
            body = r.read()
            print(f"  [✓] HTTP {r.status} {p}  ({len(body)} bytes)")
            pass_count += 1
            break
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 307, 308):
                print(f"  [✓] HTTP {e.code} {p}")
                pass_count += 1
                break
            else:
                if retry < 2:
                    time.sleep(5)
                    continue
                print(f"  [✗] HTTP {e.code} {p}")
                break
        except Exception as e:
            if retry < 2:
                time.sleep(5)
                continue
            print(f"  [✗] {type(e).__name__} {p}: {e}")
            break

print("\n" + "=" * 60)
print(f"smoke 结果：{pass_count}/{len(paths)} 通过")
print("=" * 60)

# 回归
print("\n回归检查：")
for p in ["/ai-home", "/design-system/index.html"]:
    try:
        req = urllib.request.Request(BASE_URL + p, headers={"User-Agent": "smoke/1.0"})
        r = urllib.request.urlopen(req, timeout=15)
        print(f"  [✓] HTTP {r.status} {p}")
    except urllib.error.HTTPError as e:
        ok = e.code in (200, 301, 302, 307, 308)
        print(f"  [{'✓' if ok else '✗'}] HTTP {e.code} {p}")
    except Exception as e:
        print(f"  [✗] {type(e).__name__} {p}")

ssh.close()
sys.exit(0 if pass_count == len(paths) else 1)
