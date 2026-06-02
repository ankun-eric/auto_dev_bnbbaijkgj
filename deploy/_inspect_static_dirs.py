"""检查服务器静态目录结构 + 历史小程序包"""
import sys
sys.path.insert(0, "deploy")
from _sshlib import run

cmds = [
    "docker inspect gateway-nginx --format '{{json .Mounts}}'",
    "ls -la /home/ubuntu/gateway/ 2>/dev/null | head",
    "ls -la /home/ubuntu/gateway/static/ 2>/dev/null | head",
    "ls -la /home/ubuntu/gateway/static/6b099ed3-7175-4a78-91f4-44570c84ed27/ 2>/dev/null | tail -20",
    "find /home/ubuntu -name 'miniprogram_*.zip' 2>/dev/null | head -5",
    "find /home/ubuntu -name '*.apk' -mtime -7 2>/dev/null | head -10",
]

for cmd in cmds:
    code, out, err = run(cmd, timeout=30)
    print("===", cmd)
    if out:
        print(out[:2000])
    if err:
        print("ERR:", err[:500])
