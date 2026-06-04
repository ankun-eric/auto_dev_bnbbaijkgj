import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE=f"https://{HOST}/autodev/{DID}"

def sh(c, cmd, t=900):
    print(f"\n$ {cmd}")
    i,o,e=c.exec_command(cmd, timeout=t)
    out=o.read().decode("utf-8","ignore"); err=e.read().decode("utf-8","ignore")
    if out.strip(): print(out[-7000:])
    if err.strip(): print("[stderr]", err[-1500:])
    return out,err

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30); print("SSH connected")

# follow redirect to get final page HTML, then grab a page chunk and search markers
sh(c, f"curl -sL {BASE}/health-metric/spo2/ -o /tmp/spo2.html -w 'final:%{{http_code}}\\n'; grep -o 'spo2-tab-page\\|spo2-status-card\\|AI 解读本次血氧\\|Spo2Page' /tmp/spo2.html | sort -u")
# search JS chunks referenced by health-metric page for spo2 marker
sh(c, f"docker exec {DID}-h5 sh -c \"grep -rl 'spo2-status-card' /app/.next 2>/dev/null | head -3\"")
sh(c, f"docker exec {DID}-h5 sh -c \"grep -ro 'AI 解读本次血氧' /app/.next 2>/dev/null | head -1\"")

# pip install pytest in backend container then run tests
sh(c, f"docker exec {DID}-backend sh -c 'pip install -q pytest pytest-asyncio httpx aiosqlite 2>&1 | tail -3' ", 600)
sh(c, f"docker exec {DID}-backend sh -c 'cd /app && python -m pytest tests/test_glu_spo2_detail_align_bp_v1_20260602.py -q 2>&1 | tail -30'", 900)

c.close(); print("\n=== VERIFY2 DONE ===")
