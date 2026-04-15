import urllib.request
import ssl

url = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/static/app_20260415_003629_8c83.apk"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

try:
    req = urllib.request.Request(url, method="HEAD")
    resp = urllib.request.urlopen(req, timeout=30, context=ctx)
    print(f"HTTP Status: {resp.status}")
    print(f"Content-Length: {resp.getheader('Content-Length')}")
    print(f"Content-Type: {resp.getheader('Content-Type')}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
except Exception as e:
    print(f"Error: {e}")
