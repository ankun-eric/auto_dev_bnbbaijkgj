"""[BUGFIX archive-list 404 2026-05-30] 远程诊断脚本：
- 列出当前部署容器
- 在容器内确认后端代码中是否包含 /api/family/member/state/list
- 通过 nginx 入口直接 curl 该接口，看实际返回
"""
from _ssh_helper import run, DEPLOY_ID

PREFIX = DEPLOY_ID

cmds = [
    f"docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep -E '{PREFIX}|gateway' | sort",
    f"docker exec {PREFIX}-backend python -c \"from app.main import app; routes=[r.path for r in app.routes if hasattr(r,'path')]; print('TOTAL:',len(routes)); print('\\n'.join([p for p in routes if 'family/member' in p]))\" 2>&1 | head -60",
    f"docker exec {PREFIX}-backend ls -la /app/app/api/family_member_v2.py 2>&1",
    f"docker exec {PREFIX}-backend grep -c 'state/list' /app/app/api/family_member_v2.py 2>&1",
    # 通过外部 nginx 直接访问该接口（应返回 401 而不是 404，如果路由已挂在 fastapi）
    f"curl -s -o /tmp/resp.txt -w 'HTTP %{{http_code}} CT=%{{content_type}}\\n' 'https://newbb.test.bangbangvip.com/autodev/{PREFIX}/api/family/member/state/list' && head -c 400 /tmp/resp.txt && echo",
    # 尝试一个一定存在的接口确认 nginx 路由 ok
    f"curl -s -o /tmp/r2.txt -w 'HTTP %{{http_code}}\\n' 'https://newbb.test.bangbangvip.com/autodev/{PREFIX}/api/health' && head -c 200 /tmp/r2.txt && echo",
    # 尝试老的、已知存在的 family 接口
    f"curl -s -o /tmp/r3.txt -w 'HTTP %{{http_code}}\\n' 'https://newbb.test.bangbangvip.com/autodev/{PREFIX}/api/family/members' && head -c 200 /tmp/r3.txt && echo",
]

for c in cmds:
    print("=" * 80)
    print("CMD:", c)
    rc, out, err = run(c, timeout=60)
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    print("RC=", rc)
