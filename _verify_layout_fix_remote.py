import paramiko

HOST, USER, PWD = "newbb.test.bangbangvip.com", "ubuntu", "Newbang888"
CN = "6b099ed3-7175-4a78-91f4-44570c84ed27-backend"

PYCODE = r'''
from app.api.health_metric_card_v1 import _rule_explain_single, _rule_explain_trend
from app.models.health_v3 import HealthMetricRecord
def mk(mt, v):
    r = HealthMetricRecord(); r.metric_type = mt; r.value_json = v; r.source = "manual"; return r
fails = 0
cases = [("heart_rate", {"value": 72}), ("heart_rate", {"value": 110}),
         ("blood_pressure", {"systolic": 120, "diastolic": 80}),
         ("blood_glucose", {"value": 5.5, "period": "fasting"}), ("spo2", {"value": 97})]
for mt, v in cases:
    c = _rule_explain_single(mt, mk(mt, v))
    for frag in ["本提示仅供参考", "不能替代专业医生诊断"]:
        if frag in c:
            print("FAIL disclaimer leak", mt, frag); fails += 1
    if not c:
        print("FAIL empty", mt); fails += 1
c = _rule_explain_single("heart_rate", mk("heart_rate", {"value": 72}))
assert "本次心率" in c and "建议" in c, "body missing"
for mt in ["heart_rate", "blood_pressure", "blood_glucose", "spo2"]:
    recs = [mk(mt, {"systolic": 120, "diastolic": 80} if mt == "blood_pressure" else {"value": 80}) for _ in range(5)]
    d = _rule_explain_trend(mt, recs, 7)
    assert set(["summary", "trend", "advice"]).issubset(d.keys())
    assert not d["summary"].startswith("建议：")
print("ALL PASS" if fails == 0 else ("FAILS=%d" % fails))
'''

cmd = "docker exec -i %s python - <<'PYEOF'\n%s\nPYEOF" % (CN, PYCODE)
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, 22, USER, PWD, timeout=30)
stdin, stdout, stderr = cli.exec_command(cmd, timeout=120)
print(stdout.read().decode("utf-8", "replace"))
e = stderr.read().decode("utf-8", "replace")
if e.strip():
    print("[STDERR]", e)
cli.close()
