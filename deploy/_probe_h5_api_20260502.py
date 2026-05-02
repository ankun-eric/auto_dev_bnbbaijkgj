# -*- coding: utf-8 -*-
"""探测 /api/h5/checkout/init 与 /api/h5/slots 在后端容器内是否注册。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{DEPLOY_ID}-backend"


def run(c, cmd, t=30):
    print(f"\n$ {cmd}")
    _i, o, e = c.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    rc = o.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err.strip():
        print("stderr:", err[-1500:])
    print(f"exit={rc}")
    return out


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    try:
        # 1. 容器内直接 curl 后端
        run(c, f"docker exec {BACKEND} curl -sf -o /dev/null -w '%{{http_code}}' 'http://localhost:8000/api/h5/checkout/init?productId=1' || echo")
        run(c, f"docker exec {BACKEND} curl -sf -o /dev/null -w '%{{http_code}}' 'http://localhost:8000/api/h5/slots?storeId=1&date=2026-05-03&productId=1' || echo")
        # 2. 看 /openapi.json 中是否有这两个 path
        run(c, f"docker exec {BACKEND} python -c \"import json,urllib.request as u; d=json.loads(u.urlopen('http://localhost:8000/openapi.json').read()); paths=list(d.get('paths',{{}}).keys()); print([p for p in paths if 'h5' in p])\"")
        # 3. 看 main.py 中是否真的 import 了 h5_checkout
        run(c, f"docker exec {BACKEND} grep -n h5_checkout /app/app/main.py")
        # 4. 看 nginx gateway 配置怎么转发 /api/h5
        run(c, "docker exec gateway cat /etc/nginx/conf.d/default.conf 2>/dev/null | grep -n -A2 -B1 h5 | head -40")
    finally:
        c.close()


if __name__ == "__main__":
    main()
