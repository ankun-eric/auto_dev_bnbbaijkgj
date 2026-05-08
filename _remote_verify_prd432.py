"""[PRD-432] 远程验证：1) DB 列已迁移 2) 路由已挂载 3) 401 鉴权对照 4) 自动化测试"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PWD, timeout=30)


def run(cmd, t=300):
    print(f"\n>>> {cmd[:140]}")
    s, o, e = ssh.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    if out:
        print(out[-3000:])
    if err:
        print("STDERR:", err[-500:])
    rc = o.channel.recv_exit_status()
    print(f"<<< exit={rc}")
    return rc, out, err


# 1) 验证新列已添加（容错：列不存在则会输出 Empty set）
sql = (
    "USE bini_health; "
    "SHOW COLUMNS FROM health_profiles LIKE 'past_history_is_none'; "
    "SHOW COLUMNS FROM health_profiles LIKE 'allergy_is_none'; "
    "SHOW COLUMNS FROM health_profiles LIKE 'medication_is_none'; "
    "SHOW COLUMNS FROM chat_messages LIKE 'consultant_target_id';"
)
run(
    f"docker exec {DEPLOY_ID}-db sh -c \"mysql -uroot -prootpassword -e \\\"{sql}\\\" 2>/dev/null\""
)

# 2) 验证路由已挂载
run(
    f"docker exec {DEPLOY_ID}-backend python -c \"from app.main import app; print([r.path for r in app.routes if 'profile_card' in str(r.path) or 'consultant' in str(r.path)])\""
)

# 3) 在容器内 pytest（试运行）
test_code = '''
import pytest
import httpx
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_profile_card_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/consultant/0/profile_card")
        assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_medications_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/v1/consultant/0/medications")
        assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_route_exists_in_app():
    paths = [r.path for r in app.routes]
    assert any("/api/v1/consultant/" in p and "profile_card" in p for p in paths)
    assert any("/api/v1/consultant/" in p and "medications" in p for p in paths)


def test_calc_age():
    from datetime import date
    from app.api.consultant_profile_card import _calc_age
    assert _calc_age(None) is None
    assert _calc_age(date(2000, 1, 1)) >= 24


def test_to_history_list():
    from app.api.consultant_profile_card import _to_history_list
    assert _to_history_list(None) == []
    assert _to_history_list([]) == []
    assert _to_history_list(["高血压", "糖尿病"]) == ["高血压", "糖尿病"]
    assert _to_history_list("青霉素") == ["青霉素"]
    assert _to_history_list("") == []


def test_build_summary():
    from app.api.consultant_profile_card import _build_summary_text
    s = _build_summary_text("女", 32, ["高血压"])
    assert "女" in s and "32" in s and "高血压" in s
    s2 = _build_summary_text(None, None, [])
    assert "未填" in s2
'''

remote_test_path = f"/home/ubuntu/{DEPLOY_ID}/backend/tests/test_prd432_profile_card.py"
sftp = ssh.open_sftp()
try:
    sftp.stat(f"/home/ubuntu/{DEPLOY_ID}/backend/tests")
except FileNotFoundError:
    run(f"mkdir -p /home/ubuntu/{DEPLOY_ID}/backend/tests")

with sftp.open(remote_test_path, "w") as f:
    f.write(test_code)
sftp.close()

print("\n[Run pytest in backend container]")
run(
    f"docker exec {DEPLOY_ID}-backend bash -lc 'pip install -q pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -5'",
    t=300,
)
run(
    f"docker cp /home/ubuntu/{DEPLOY_ID}/backend/tests/test_prd432_profile_card.py {DEPLOY_ID}-backend:/app/test_prd432_profile_card.py"
)
run(
    f"docker exec -w /app {DEPLOY_ID}-backend python -m pytest test_prd432_profile_card.py -v 2>&1 | tail -60",
    t=300,
)

ssh.close()
print("\n[OK] verify done")
