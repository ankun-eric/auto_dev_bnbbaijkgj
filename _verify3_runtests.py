import paramiko
HOST="newbb.test.bangbangvip.com"; USER="ubuntu"; PWD="Newbang888"
DID="6b099ed3-7175-4a78-91f4-44570c84ed27"; PROJ=f"/home/ubuntu/{DID}"

def sh(c, cmd, t=900):
    print(f"\n$ {cmd}")
    i,o,e=c.exec_command(cmd, timeout=t)
    out=o.read().decode("utf-8","ignore"); err=e.read().decode("utf-8","ignore")
    if out.strip(): print(out[-8000:])
    if err.strip(): print("[stderr]", err[-1500:])
    return out,err

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=30); print("SSH connected")

sh(c, f"docker cp {PROJ}/backend/tests/test_glu_spo2_detail_align_bp_v1_20260602.py {DID}-backend:/app/tests/test_glu_spo2_detail_align_bp_v1_20260602.py")
# the test _read() checks dirname/../../<rel> (=> /h5-web/...) and /app/<rel>. Copy h5-web + miniprogram source to /h5-web and /miniprogram inside container so static asserts run (not skip).
sh(c, f"docker exec {DID}-backend sh -c 'rm -rf /h5-web /miniprogram; mkdir -p /h5-web/src/app /h5-web/src/lib /miniprogram/pages/health-metric'")
sh(c, f"docker cp {PROJ}/h5-web/src/app/health-metric {DID}-backend:/h5-web/src/app/health-metric")
sh(c, f"docker cp {PROJ}/h5-web/src/lib/spo2-level.ts {DID}-backend:/h5-web/src/lib/spo2-level.ts")
sh(c, f"docker cp {PROJ}/miniprogram/pages/health-metric/index.wxml {DID}-backend:/miniprogram/pages/health-metric/index.wxml")
sh(c, f"docker exec {DID}-backend sh -c 'cd /app && python -m pytest tests/test_glu_spo2_detail_align_bp_v1_20260602.py -q 2>&1 | tail -20'", 900)

c.close(); print("\n=== VERIFY3 DONE ===")
