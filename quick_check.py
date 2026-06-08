"""Quick URL check using subprocess curl."""
import subprocess
import json

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"

urls = [
    # Frontend pages (critical path)
    ("PAGE", "/"),
    ("PAGE", "/ai-home"),
    ("PAGE", "/ai-home/medication-reminder"),
    ("PAGE", "/ai-home/medication-reminder/history"),
    ("PAGE", "/login"),
    ("PAGE", "/health-profile"),
    ("PAGE", "/health-dashboard"),
    ("PAGE", "/health-plan"),
    ("PAGE", "/messages"),
    ("PAGE", "/settings"),
    ("PAGE", "/products"),
    ("PAGE", "/services"),
    ("PAGE", "/points"),
    ("PAGE", "/news"),
    ("PAGE", "/checkup"),
    ("PAGE", "/drug"),
    ("PAGE", "/tcm"),
    ("PAGE", "/glucose"),
    ("PAGE", "/brain-game"),
    ("PAGE", "/home-safety"),
    ("PAGE", "/devices"),
    ("PAGE", "/medical-records"),
    ("PAGE", "/care-ai-home"),
    ("PAGE", "/cards"),
    ("PAGE", "/merchant/login"),
    ("PAGE", "/health-plan/checkin"),
    ("PAGE", "/ai-home/medication-plans"),
    ("PAGE", "/ai-home/medication-plans/new"),
    ("PAGE", "/health-plan/custom"),
    ("PAGE", "/checkup/compare"),
    
    # Backend APIs
    ("API", "/api/health"),
    ("API", "/api/medication/calendar?year=2026&month=6"),
    ("API", "/api/medication/records?date=2026-06-07"),
    ("API", "/api/medication/today"),
    ("API", "/api/medication-reminder/plans"),
    ("API", "/api/medication-reminder/today"),
    ("API", "/api/medication-reminder/badge"),
    ("API", "/api/medication-plans/today"),
    ("API", "/api/medication-plans/hero-count"),
    ("API", "/api/medication-check-in"),
    ("API", "/api/auth/login"),
    ("API", "/api/health-plan"),
    ("API", "/api/bottom-nav"),
    ("API", "/api/home-config"),
    ("API", "/api/ai-home/config"),
    ("API", "/api/family/members"),
    ("API", "/api/points/balance"),
    ("API", "/api/orders/unified"),
    ("API", "/api/products"),
    ("API", "/api/services"),
    ("API", "/api/notifications"),
    ("API", "/api/messages/unread"),
    ("API", "/api/chat/sessions"),
    ("API", "/api/tcm/constitution"),
    ("API", "/api/health-dashboard"),
    ("API", "/api/glucose"),
    ("API", "/api/brain-game"),
    ("API", "/api/home-safety"),
    ("API", "/api/devices"),
    ("API", "/api/ocr"),
    ("API", "/api/scan"),
    ("API", "/api/report"),
    ("API", "/api/coupons"),
    ("API", "/api/cards"),
    ("API", "/api/membership"),
]

results = []
for i, (typ, path) in enumerate(urls):
    full_url = f"{BASE}{path}"
    try:
        r = subprocess.run([
            "curl", "-sL", "--connect-timeout", "5", "--max-time", "15",
            "-o", "NUL", "-w", "%{http_code}|%{num_redirects}|%{url_effective}",
            full_url
        ], capture_output=True, text=True, timeout=20)
        out = r.stdout.strip()
        parts = out.split("|")
        status = int(parts[0]) if parts[0].isdigit() else 0
        redirects = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        final = parts[2] if len(parts) > 2 else full_url
        ok = status in (200, 201, 202, 204, 304, 405)
        print(f"[{i+1:03d}/{len(urls)}] {'✅' if ok else '❌'} {status:03d} ({redirects}r) {typ:4s} {path}")
        results.append({"type": typ, "path": path, "status": status, "redirects": redirects, "ok": ok})
    except Exception as e:
        print(f"[{i+1:03d}/{len(urls)}] ❌ ERR {typ:4s} {path} - {str(e)[:100]}")
        results.append({"type": typ, "path": path, "status": 0, "redirects": 0, "ok": False, "error": str(e)[:200]})

ok_count = sum(1 for r in results if r["ok"])
fail_count = len(results) - ok_count
print(f"\n总计: {len(results)}, ✅ {ok_count}, ❌ {fail_count}")

print("\n=== 不可达 URL ===")
for r in results:
    if not r["ok"]:
        print(f"  {r['type']} {r.get('status','ERR')} {BASE}{r['path']}")

with open("C:\\auto_output\\bnbbaijkgj\\check_results.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
