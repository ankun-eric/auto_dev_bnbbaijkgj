import urllib.request

url = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/app_20260428_010702_622e.apk"
print(f"Checking: {url}")

try:
    req = urllib.request.Request(url, method='HEAD')
    r = urllib.request.urlopen(req, timeout=15)
    print(f"Status: {r.status}")
    cl = r.headers.get('Content-Length', 'unknown')
    ct = r.headers.get('Content-Type', 'unknown')
    print(f"Content-Length: {cl}")
    print(f"Content-Type: {ct}")
    if r.status == 200:
        size_mb = int(cl) / 1024 / 1024 if cl != 'unknown' else 0
        print(f"\nSUCCESS! APK is accessible ({size_mb:.1f} MB)")
        print(f"\nDownload URL: {url}")
except Exception as e:
    print(f"ERROR: {e}")
