"""[BUGFIX archive-list 404 2026-05-30] 在容器内运行 family_member 状态机相关回归测试"""
from _ssh_helper import run, DEPLOY_ID

cmds = [
    # 主测试：state machine v1
    f"docker exec {DEPLOY_ID}-backend bash -c 'cd /app && python -m pytest tests/test_family_member_state_machine_v1_20260529.py -x --tb=short 2>&1' | tail -120",
    # member family v11 也相关
    f"docker exec {DEPLOY_ID}-backend bash -c 'cd /app && python -m pytest tests/test_member_family_member_v11_20260530.py -x --tb=short 2>&1' | tail -80",
    # family v2 base
    f"docker exec {DEPLOY_ID}-backend bash -c 'cd /app && python -m pytest tests/test_family_member_v2_20260518.py -x --tb=short 2>&1' | tail -80",
]

for c in cmds:
    print("="*100); print("CMD:", c[:160])
    rc, out, err = run(c, timeout=600)
    print(out)
    if err: print("ERR:", err)
    print("RC=", rc)
