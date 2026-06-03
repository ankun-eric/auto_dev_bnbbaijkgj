from _ssh_helper import run

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

cmds = [
    # 1. Smoke v2 callback endpoint
    f"curl -sk -w '\\nHTTP %{{http_code}}\\n' {BASE}/api/home_safety/callback/alarm -X POST -H 'Content-Type: application/json' --data '{{\"msgId\":\"smoke_v2_1\",\"param\":{{\"devId\":\"NOEXIST1\",\"devType\":1,\"occurTime\":1547100617645}},\"dataType\":\"call-msg\"}}'",
    # 2. push_history endpoint requires auth → should be 401
    f"curl -sk -w '\\nHTTP %{{http_code}}\\n' {BASE}/api/admin/home_safety/callback_config/push_history",
]
for c in cmds:
    rc, out, err = run(c, timeout=20)
    print("CMD:", c[:90])
    print("OUT:", out, "ERR:", err)
    print("---")
