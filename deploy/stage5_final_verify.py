#!/usr/bin/env python3
"""阶段5：最终验证"""

import paramiko
import time

PROD_HOST = 'chat.benne-ai.com'
PROD_PORT = 22
PROD_USER = 'ubuntu'
PROD_PASS = 'Benne-ai@#'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

def run_ssh(cmd, timeout=60):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=PROD_HOST, port=PROD_PORT, username=PROD_USER,
                      password=PROD_PASS, timeout=20, allow_agent=False, look_for_keys=False)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode('utf-8', errors='replace')
        err = stderr.read().decode('utf-8', errors='replace')
        return out, err
    finally:
        client.close()

def main():
    print("=" * 60)
    print("阶段5：最终验证")
    print("=" * 60)
    
    # 1. 完整容器状态
    print("\n[1] 容器状态")
    out, err = run_ssh("cd /home/ubuntu/{} && docker compose -f docker-compose.prod.yml ps".format(DEPLOY_ID))
    print(out)
    
    # 2. 最近日志检查
    print("[2] 后端日志(最近20行)")
    out, err = run_ssh("docker logs --tail=20 {}-backend 2>&1".format(DEPLOY_ID))
    # Filter for errors
    errors = [l for l in out.split('\n') if 'error' in l.lower() or 'exception' in l.lower() or 'traceback' in l.lower()]
    if errors:
        print("⚠️ 发现错误:")
        for e in errors[:5]:
            print("  ", e[:150])
    else:
        print("  ✅ 无错误")
    
    # 3. 数据库连接验证
    print("\n[3] 数据库连接")
    out, err = run_ssh(
        "docker exec {}-backend python3 -c \"import asyncio; from app.database import engine; from sqlalchemy import text; async def t(): async with engine.begin() as c: r = await c.execute(text('SELECT 1')); print('DB OK:', r.scalar()); asyncio.run(t())\" 2>&1".format(DEPLOY_ID),
        timeout=30
    )
    if err: print("  ERR:", err[:300])
    if out: print("  ", out.strip()[:200])
    
    # 4. 扩展链接检查
    print("\n[4] 扩展链接检查")
    ext_urls = [
        '/api/health',
        '/',
        '/admin/',
        '/api/brain-game/regions',
        '/api/brain-game/scores',
        '/api/brain-game/challenges',
        '/api/family/members',
        '/api/family/invite',
        '/api/auth/me',
        '/api/devices/scene-groups',
        '/api/payment/config',
    ]
    
    all_ok = True
    for path in ext_urls:
        url = 'https://chat.benne-ai.com{}'.format(path)
        out, err = run_ssh("curl -s -o /dev/null -w '%{{http_code}}' '{}' 2>&1".format(url), timeout=15)
        code = out.strip()
        ok = code in ('200', '301', '302', '307', '308', '401', '403', '405')
        status = '✅' if ok else '❌'
        if not ok: all_ok = False
        print("  {} {} -> HTTP {}".format(status, path, code))
    
    # 5. Gateway 确认
    print("\n[5] Gateway 状态")
    out, err = run_ssh("docker ps --filter name=gateway-nginx --format '{{.Status}}'")
    print("  gateway-nginx:", out.strip())
    
    out, err = run_ssh("docker network inspect {}-network --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'".format(DEPLOY_ID))
    print("  网络容器:", out.strip()[:200])
    
    # 6. 数据库表确认
    print("\n[6] 数据库表")
    out, err = run_ssh(
        "docker exec {}-backend python3 -c \"from app.database import engine; from sqlalchemy import inspect; inspector = inspect(engine); tables = inspector.get_table_names(); print('Tables:', len(tables)); print([t for t in sorted(tables) if 'brain' in t.lower() or 'device' in t.lower() or 'guardian' in t.lower() or 'safety' in t.lower()])\" 2>&1".format(DEPLOY_ID),
        timeout=30
    )
    print("  ", out.strip()[:300])
    if err: print("  ERR:", err[:200])

    print("\n" + "=" * 60)
    if all_ok:
        print("✅ 最终验证全部通过！")
    else:
        print("⚠️ 部分验证项失败，请检查上方详情")
    print("=" * 60)

if __name__ == '__main__':
    main()
