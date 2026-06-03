"""[PRD-HEALTH-METRIC-CARD-UNIFY-V1] 端到端冒烟测试。

测试维度：
1. 后端 /api/health-metric-v1/meta 返回 200 + 四指标元数据
2. H5 路由 /health-metric/blood_pressure/history?profileId=xxx 返回 200（页面 SSR 成功）
3. H5 路由 /health-metric/blood_glucose/history?profileId=xxx 返回 200
4. H5 路由 /health-metric/heart_rate/history?profileId=xxx 返回 200
5. H5 路由 /health-metric/spo2/history?profileId=xxx 返回 200
"""
import paramiko, json

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

def run(cmd, timeout=30):
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', 'replace'), stderr.read().decode('utf-8', 'replace')


results = []

# 1. /meta
print("[1] GET /api/health-metric-v1/meta")
out, err = run(f"curl -sS '{BASE}/api/health-metric-v1/meta' -o /tmp/meta.json && cat /tmp/meta.json")
try:
    body = json.loads(out)
    metric_types = set(body.get("data", {}).get("metric_types", []))
    expected = {"blood_pressure", "blood_glucose", "heart_rate", "spo2"}
    if metric_types == expected:
        print(f"  ✓ 四指标 metric_types 齐全（含 spo2 血氧）")
        results.append(True)
    else:
        print(f"  ✗ metric_types 不齐：{metric_types}")
        results.append(False)
except Exception as e:
    print(f"  ✗ 响应解析失败：{e}\n  原始：{out[:300]}")
    results.append(False)

# 2-5. H5 路由
for mt in ["blood_pressure", "blood_glucose", "heart_rate", "spo2"]:
    url = f"{BASE}/health-metric/{mt}/history?profileId=1"
    print(f"[*] GET {url}")
    out, err = run(f"curl -sS -L -o /dev/null -w 'HTTP:%{{http_code}}' '{url}'")
    if "HTTP:200" in out:
        print(f"  ✓ {mt} 全部历史页可访问")
        results.append(True)
    else:
        print(f"  ✗ {mt} 失败：{out.strip()}")
        results.append(False)

# 6. AI 解读接口结构（401 也算路由存在）
print(f"[6] POST /api/health-metric-v1/1/spo2/ai-explain-trend")
out, err = run(f"curl -sS -X POST '{BASE}/api/health-metric-v1/1/spo2/ai-explain-trend' -H 'Content-Type: application/json' -d '{{\"range\":\"7d\"}}' -w '\\nHTTP:%{{http_code}}'")
if "HTTP:401" in out or "HTTP:403" in out or "HTTP:200" in out:
    print(f"  ✓ AI 解读趋势接口路由存在（{out.strip().split(chr(10))[-1]}）")
    results.append(True)
else:
    print(f"  ✗ {out.strip()[:200]}")
    results.append(False)

cli.close()
total = len(results)
passed = sum(results)
print(f"\n[SMOKE TEST] {passed}/{total} passed")
exit(0 if passed == total else 1)
