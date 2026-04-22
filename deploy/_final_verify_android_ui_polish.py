import urllib.request, json

URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/static/downloads/app_20260423_021006_3b7d.apk"
req = urllib.request.Request(URL, method="HEAD")
with urllib.request.urlopen(req, timeout=30) as r:
    result = {
        "status": r.status,
        "content_length": int(r.headers.get("Content-Length", "0")),
        "content_type": r.headers.get("Content-Type"),
        "url": URL,
    }
result["ok"] = result["status"] == 200 and result["content_length"] > 1024 * 1024
print(json.dumps(result, indent=2))
