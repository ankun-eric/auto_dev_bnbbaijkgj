"""检查容器中 main.py 是否包含 family_member_v2 注册段"""
from _ssh_helper import run, DEPLOY_ID

cmds = [
    f"docker exec {DEPLOY_ID}-backend grep -n 'family_member_v2\\|/api/family/member/state' /app/app/main.py 2>&1 | head -30",
    f"docker exec {DEPLOY_ID}-backend wc -l /app/app/main.py",
    # 在容器内直接重新构造 app，看路由是不是真有
    f"docker exec {DEPLOY_ID}-backend python -c \"import sys; from app.main import app; ps=[r.path for r in app.routes if hasattr(r,'path') and 'state/list' in r.path]; print('matching:', ps)\" 2>&1 | tail -5",
]
for c in cmds:
    print("="*80); print("CMD:", c[:180])
    rc,out,err = run(c, timeout=60)
    print(out); 
    if err: print("ERR:", err)
    print("RC=", rc)
