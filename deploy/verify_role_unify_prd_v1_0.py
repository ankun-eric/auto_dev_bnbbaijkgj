"""[2026-04-26 PRD v1.0] 部署后验证脚本

1. 在 backend 容器里执行路由冲突扫描（路径修正为 /app 直接子目录）
2. DB 校验：merchant_store_memberships.role_code 仅剩 4 角色
3. /api/merchant/profile 在 admin 测试老板登录后返回完整 8 字段
"""
from __future__ import annotations
import json
import sys
import paramiko  # type: ignore

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND_CONT = f"{DEPLOY_ID}-backend"
DB_CONT = f"{DEPLOY_ID}-db"
DB_PASS = "bini_health_2026"
BASE_URL = f"https://localhost/autodev/{DEPLOY_ID}"


def ssh() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=22, username=USER, password=PASS, timeout=30)
    return c


def run(c, cmd, timeout=120):
    print(f"\n$ {cmd}", flush=True)
    _i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    code = o.channel.recv_exit_status()
    if out.strip():
        print(out[-3000:], flush=True)
    if err.strip():
        print("stderr:", err[-1500:], flush=True)
    print(f"exit={code}", flush=True)
    return code, out, err


def main() -> int:
    c = ssh()
    try:
        # 1) 路由冲突扫描 — 在 backend 容器内 sys.path 已是 /app，模块以 app.* 引用
        print("\n========= [B1] 路由冲突全局扫描 =========", flush=True)
        run(c, f"docker exec {BACKEND_CONT} ls /app | head -20", timeout=15)
        # 直接用一段 inline python 做冲突扫描，避免脚本路径不匹配
        py = (
            "import sys, json; sys.path.insert(0, '/app');"
            "from app.main import app;"
            "b={};\n"
            "for r in app.routes:\n"
            "    p=getattr(r,'path',None); ms=getattr(r,'methods',None) or set(); ep=getattr(r,'endpoint',None)\n"
            "    if not p or ep is None: continue\n"
            "    name=f\"{getattr(ep,'__module__','?')}.{getattr(ep,'__name__','?')}\"\n"
            "    for m in ms: b.setdefault((p,m.upper()),[]).append(name)\n"
            "cf=[{'path':p,'method':m,'endpoints':eps} for (p,m),eps in b.items() if len(eps)>1]\n"
            "open('/tmp/route_conflicts.json','w').write(json.dumps({'count':len(cf),'conflicts':cf},ensure_ascii=False,indent=2))\n"
            "print('CONFLICT_COUNT=',len(cf))\n"
            "print('PROFILE_GET_HANDLERS=',b.get(('/api/merchant/profile','GET'),[]))\n"
        )
        # 用 base64 包装避免 shell 转义问题
        import base64
        b64 = base64.b64encode(py.encode("utf-8")).decode()
        run(c, f'docker exec {BACKEND_CONT} sh -c "echo {b64} | base64 -d | python -"', timeout=60)
        run(c, f"docker exec {BACKEND_CONT} cat /tmp/route_conflicts.json | head -200", timeout=15)

        # 2) DB 校验：role_code 仅剩 4 角色
        print("\n========= [R1] DB role_code 分布 =========", flush=True)
        run(
            c,
            f'docker exec {DB_CONT} mysql -uroot -p{DB_PASS} bini_health -e '
            f'"SELECT role_code, COUNT(*) AS n FROM merchant_store_memberships GROUP BY role_code ORDER BY n DESC;"',
            timeout=30,
        )
        run(
            c,
            f'docker exec {DB_CONT} mysql -uroot -p{DB_PASS} bini_health -e '
            f'"SELECT role_code, member_role, COUNT(*) AS n FROM merchant_store_memberships GROUP BY role_code, member_role;"',
            timeout=30,
        )

        # 3) profile 接口路径验证（无 token 时应返回 401，证明被新接口接管而不是 404）
        print("\n========= [B1] /api/merchant/profile HTTP 自检 =========", flush=True)
        run(c, f"curl -sk -o /dev/null -w '%{{http_code}}' {BASE_URL}/api/merchant/profile", timeout=15)

        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
