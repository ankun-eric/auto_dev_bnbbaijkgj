# -*- coding: utf-8 -*-
import urllib.request, ssl
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"
candidates = [
    f"{BASE}/bini_health_android-v20260504-023553-87ac.apk",
    f"{BASE}/static/apk/bini_health_android_bug367_20260507_112853.apk",
    f"{BASE}/apk/bini_health_android_bug367_20260507_112853.apk",
    f"{BASE}/static/bini_health_android_bug367_20260507_112853.apk",
    f"{BASE}/static/apk/bini_health_android_login_layout_20260506_004240_45e7.apk",
]
for u in candidates:
    try:
        req = urllib.request.Request(u, method="HEAD")
        r = urllib.request.urlopen(req, timeout=20, context=ctx)
        print(r.getcode(), r.headers.get("Content-Length"), u)
    except Exception as e:
        print("ERR", e, u)
