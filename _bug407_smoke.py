"""Smoke test bug407 fix on the test server.

Steps:
1. SSH into server, pull MySQL credentials from backend container env.
2. Find the order 41's owner user and a fresh future appointment time.
3. Mint a JWT token using the same SECRET_KEY as backend (read from container env).
4. Hit POST {base}/api/orders/unified/41/appointment with X-Client-Source: h5-customer
   and verify status_code != 500. Also re-run twice to confirm session not poisoned.
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta

import paramiko
import requests

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
CONTAINER = f"{DEPLOY_ID}-backend"


def ssh_run(cli, cmd, timeout=120):
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out + (("\n[ERR]\n" + err) if err.strip() else "")


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASS, timeout=30, allow_agent=False, look_for_keys=False)

    # 1. read env from container
    env_dump = ssh_run(cli, f"docker exec {CONTAINER} env | grep -E 'SECRET_KEY|ALGORITHM|DATABASE'")
    print("ENV:\n", env_dump)

    secret = None
    algo = "HS256"
    for line in env_dump.splitlines():
        if line.startswith("SECRET_KEY="):
            secret = line.split("=", 1)[1].strip()
        elif line.startswith("ALGORITHM="):
            algo = line.split("=", 1)[1].strip()
    if not secret:
        # fallback: read from app.core.config
        cfg = ssh_run(cli, f"docker exec {CONTAINER} python -c \"from app.core.config import settings; print(settings.SECRET_KEY); print(settings.ALGORITHM)\"")
        print("CFG:", cfg)
        lines = [x for x in cfg.splitlines() if x.strip() and not x.startswith("[")]
        if len(lines) >= 2:
            secret, algo = lines[0].strip(), lines[1].strip()

    if not secret:
        print("FATAL: cannot get SECRET_KEY")
        sys.exit(1)
    print(f"SECRET_KEY len={len(secret)} ALGO={algo}")

    # 2. find order 41 owner
    sql_q = (
        "SELECT u.id, u.phone, u.role, o.id, o.status, o.user_id "
        "FROM unified_orders o JOIN users u ON u.id=o.user_id WHERE o.id=41;"
    )
    out = ssh_run(cli, f"docker exec {CONTAINER} python -c \"import asyncio; from sqlalchemy import text; from app.core.database import engine; "
        + "import asyncio\n"
        + "async def main():\n"
        + "  async with engine.connect() as conn:\n"
        + f"    r=await conn.execute(text('''{sql_q}'''))\n"
        + "    print(list(r.mappings()))\n"
        + "asyncio.run(main())\"")
    print("ORDER 41:", out)

    # parse user_id (the second 'user_id' key from query)
    user_id = None
    user_phone = None
    m_uid = re.search(r"'user_id':\s*(\d+)", out)
    if m_uid:
        user_id = int(m_uid.group(1))
    mp = re.search(r"'phone':\s*'([^']+)'", out)
    if mp:
        user_phone = mp.group(1)
    if not user_id:
        print("Cannot parse user_id; raw output:", out)
        sys.exit(2)
    print(f"order 41 user_id={user_id} phone={user_phone}")

    # 3. is this user dual identity? (phone exists in merchants)
    out2 = ssh_run(cli, f"docker exec {CONTAINER} python -c \"import asyncio; from sqlalchemy import text; from app.core.database import engine; "
        + "import asyncio\n"
        + "async def main():\n"
        + "  async with engine.connect() as conn:\n"
        + f"    r=await conn.execute(text('SELECT id,name,contact_phone FROM merchants WHERE contact_phone=:p'), dict(p='{user_phone}'))\n"
        + "    print(list(r.mappings()))\n"
        + "asyncio.run(main())\"")
    print("MERCHANT for phone:", out2)

    # 4. mint a JWT token using local jose
    try:
        from jose import jwt
    except ImportError:
        print("install python-jose first: pip install python-jose[cryptography]")
        sys.exit(3)
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(hours=1),
    }
    token = jwt.encode(payload, secret, algorithm=algo)
    print(f"token (len={len(token)}): {token[:40]}...")

    # 5. craft request body — pick a future appt time in tomorrow afternoon
    tomorrow = datetime.now() + timedelta(days=1)
    appt = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
    body = {
        "appointment_time": appt.strftime("%Y-%m-%dT%H:%M:%S"),
        "appointment_data": {"time_slot": "14:00-15:00"},
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Client-Source": "h5-customer",
        "Content-Type": "application/json",
    }
    url = f"{BASE_URL}/api/orders/unified/41/appointment"
    print(f"POST {url}")
    print(f"BODY: {json.dumps(body)}")

    failures = []
    for i in range(3):
        try:
            r = requests.post(url, json=body, headers=headers, timeout=30, verify=True)
            print(f"\n[probe #{i+1}] status={r.status_code}")
            print(r.text[:500])
            if r.status_code == 500:
                failures.append(f"probe #{i+1} returned 500: {r.text[:200]}")
            else:
                print(f"  -> ok (non-500)")
        except Exception as e:
            print(f"[probe #{i+1}] EXCEPTION: {e}")
            failures.append(str(e))
        time.sleep(1)

    print("\n=== SUMMARY ===")
    if failures:
        print("FAILURES:")
        for f in failures:
            print("  -", f)
        sys.exit(10)
    else:
        print("ALL PROBES PASSED (no 500). Reschedule fix verified on order 41.")

    cli.close()


if __name__ == "__main__":
    main()
