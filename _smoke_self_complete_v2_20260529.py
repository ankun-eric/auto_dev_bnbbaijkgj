"""[BUG_FIX 2026-05-29] 真实环境 smoke：直接命中线上接口验证 v2 兜底逻辑

策略：
1. 在容器内创建几个测试 user，分别构造三类场景：
   A) 仅 family_member(is_self=1) 有数据 → 期望 needComplete=false
   B) 全空 → 期望 needComplete=true
   C) 占位 nickname=本人 + 无任何资料 → 期望 needComplete=true
2. 通过 /api/auth/login 拿 token
3. 调 GET /api/health-profile/self 判断
"""
import json
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PWD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'

s = paramiko.SSHClient()
s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect(HOST, username=USER, password=PWD, timeout=30)


def run(cmd, t=120):
    print('\n>>>', cmd[:300])
    _, out, err = s.exec_command(cmd, timeout=t)
    o = out.read().decode('utf-8', 'replace')
    e = err.read().decode('utf-8', 'replace')
    code = out.channel.recv_exit_status()
    if o:
        print(o[-6000:])
    if e:
        print('STDERR:', e[-2000:])
    print('[exit=', code, ']')
    return code, o


# 构造测试数据脚本，写入容器
fixture_py = r'''
import asyncio
from datetime import date
from sqlalchemy import select, delete
from app.core.database import async_session
from app.core.security import get_password_hash
from app.models.models import User, FamilyMember, HealthProfile, UserRole

PHONES = ["13900099001", "13900099002", "13900099003"]

async def main():
    async with async_session() as s:
        # 清理
        for ph in PHONES:
            r = await s.execute(select(User).where(User.phone == ph))
            u = r.scalar_one_or_none()
            if u:
                await s.execute(delete(HealthProfile).where(HealthProfile.user_id == u.id))
                await s.execute(delete(FamilyMember).where(FamilyMember.user_id == u.id))
                await s.execute(delete(User).where(User.id == u.id))
        await s.commit()

        # 场景 A：family_members(is_self) 上有 nickname/gender/birthday，HealthProfile 无 self 记录
        u_a = User(phone=PHONES[0], password_hash=get_password_hash("p123"), nickname="A", role=UserRole.user)
        s.add(u_a); await s.flush()
        s.add(FamilyMember(user_id=u_a.id, relationship_type="本人", nickname="陈A", gender="男",
                           birthday=date(1980, 3, 3), is_self=True, status="active"))

        # 场景 B：全空（仅占位）
        u_b = User(phone=PHONES[1], password_hash=get_password_hash("p123"), nickname="B", role=UserRole.user)
        s.add(u_b); await s.flush()
        s.add(FamilyMember(user_id=u_b.id, relationship_type="本人", nickname="本人",
                           is_self=True, status="active"))

        # 场景 C：HealthProfile 有 name/gender，缺 birthday，但 family_members(is_self) 上有 birthday
        u_c = User(phone=PHONES[2], password_hash=get_password_hash("p123"), nickname="C", role=UserRole.user)
        s.add(u_c); await s.flush()
        s.add(FamilyMember(user_id=u_c.id, relationship_type="本人", nickname="本人",
                           birthday=date(1990, 9, 9), is_self=True, status="active"))
        s.add(HealthProfile(user_id=u_c.id, family_member_id=None, name="周C", gender="女", birthday=None))

        await s.commit()
        print("FIXTURE READY:", PHONES)

asyncio.run(main())
'''

with open('_fixture_self_complete_v2.py', 'w', encoding='utf-8') as f:
    f.write(fixture_py)

# 上传 fixture
sftp = s.open_sftp()
sftp.put('_fixture_self_complete_v2.py',
         f'/home/ubuntu/{DEPLOY_ID}/_fixture_self_complete_v2.py')
run(f'docker cp /home/ubuntu/{DEPLOY_ID}/_fixture_self_complete_v2.py {DEPLOY_ID}-backend:/app/_fixture_self_complete_v2.py')
run(f'docker exec {DEPLOY_ID}-backend python /app/_fixture_self_complete_v2.py 2>&1 | tail -20', t=120)

# 现在通过 nginx 访问，模拟 H5 端登录 + 拉 self
BASE = f'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}'
expected = {
    "13900099001": ("A 仅 family_member 有数据", False),
    "13900099002": ("B 全空（占位）", True),
    "13900099003": ("C 跨表并集补齐 birthday", False),
}

results = []
for phone, (desc, expect_need) in expected.items():
    print(f"\n===== 场景：{desc} (phone={phone}, expect needComplete={expect_need}) =====")
    code, out = run(
        f'curl -sLk -X POST {BASE}/api/auth/login -H "Content-Type: application/json" '
        f'-d \'{{"phone":"{phone}","password":"p123"}}\''
    )
    try:
        login = json.loads(out)
    except Exception:
        print("LOGIN PARSE FAIL", out)
        results.append((phone, desc, "LOGIN_FAIL"))
        continue
    token = login.get("access_token") or login.get("token") or (login.get("data") or {}).get("access_token")
    if not token:
        print("NO TOKEN:", login)
        results.append((phone, desc, "NO_TOKEN"))
        continue
    code, out = run(
        f'curl -sLk {BASE}/api/health-profile/self -H "Authorization: Bearer {token}" -H "Client-Type: h5-user"'
    )
    try:
        body = json.loads(out)
    except Exception:
        print("RESP PARSE FAIL", out)
        results.append((phone, desc, "RESP_FAIL"))
        continue
    data = body.get("data") or {}
    actual = bool(data.get("needComplete"))
    missing = data.get("missingFields")
    ok = (actual == expect_need)
    print(f"  needComplete={actual} (expect={expect_need}), missing={missing}, OK={ok}")
    results.append((phone, desc, "PASS" if ok else f"FAIL actual={actual} missing={missing}"))

print("\n\n========== SMOKE 汇总 ==========")
fail = 0
for phone, desc, st in results:
    print(f"  [{st}] {phone}  {desc}")
    if not st.startswith("PASS"):
        fail += 1
print(f"\n{'ALL PASS' if fail == 0 else f'{fail} FAILED'}")

s.close()
