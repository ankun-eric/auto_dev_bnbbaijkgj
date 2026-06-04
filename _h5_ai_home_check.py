"""验证 h5 ai-home 编译产物与新代码已经合并"""
import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

# 1. h5 容器内的 ai-home 静态 chunk 包含新 resolveButtonIntent 标识吗
cmds = [
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 ls /app/.next/server/app/\\(ai-chat\\)/ai-home/',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 find /app/.next/static -name "*.js" | head -5',
    # 在 chunks 中搜新加 marker
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 grep -l "BUG_FIX_REPORT_DRUG_BUTTON_INTENT_MAPPING_20260525" /app/.next 2>/dev/null -r | head -5',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 grep -l "resolveButtonIntent" /app/.next -r 2>/dev/null | head -5',
]
for cmd in cmds:
    print(f"$ {cmd}")
    _, o, e = c.exec_command(cmd, timeout=60)
    so = o.read().decode().strip()
    se = e.read().decode().strip()
    if so: print(so)
    if se: print(f"[stderr] {se}")
    print()
c.close()
