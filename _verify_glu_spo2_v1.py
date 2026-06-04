import paramiko, time
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"; PROJ=f"/home/ubuntu/{DID}"
BASE=f"https://{HOST}/autodev/{DID}"

def sh(c, cmd, t=600):
    print(f"\n$ {cmd}")
    i,o,e=c.exec_command(cmd, timeout=t)
    out=o.read().decode("utf-8","ignore"); err=e.read().decode("utf-8","ignore")
    if out.strip(): print(out[-6000:])
    if err.strip(): print("[stderr]", err[-1500:])
    return out,err

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30)
print("SSH connected")

# external URL checks via curl from server (https with real domain)
for path in ["/", "/login", "/health-profile", "/health-metric/spo2", "/health-metric/blood_glucose", "/api/health"]:
    sh(c, f"curl -s -o /dev/null -w '%{{http_code}}' {BASE}{path}; echo '  <- {path}'", 60)

# verify deployed page bundle contains new spo2 testids (server-side gateway, allow -k)
sh(c, f"curl -s {BASE}/health-metric/spo2 | grep -o 'spo2-tab-page\\|spo2-status-card\\|AI 解读本次血氧' | sort -u | head", 60)

# run backend tests inside backend container
sh(c, f"docker exec {DID}-backend python -m pytest tests/test_glu_spo2_detail_align_bp_v1_20260602.py -q 2>&1 | tail -25", 600)

c.close(); print("\n=== VERIFY DONE ===")
