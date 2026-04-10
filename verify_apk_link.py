import urllib.request
import ssl

url = "https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/bini_health_android-v20260410-142406-uqk2.apk"
try:
    req = urllib.request.Request(url, method="HEAD")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    cl = resp.headers.get("Content-Length", "unknown")
    ct = resp.headers.get("Content-Type", "unknown")
    print(f"Status: {resp.status}")
    print(f"Content-Length: {cl}")
    print(f"Content-Type: {ct}")
    print("Download link is REACHABLE")
except Exception as e:
    print(f"Error: {e}")
