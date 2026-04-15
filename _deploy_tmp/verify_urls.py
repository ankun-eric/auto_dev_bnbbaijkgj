import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_none = False

urls = [
    'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/static/miniprogram_20260415_003643_6966.zip',
    'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/static/verify_miniprogram_20260415_003646_7b16.zip',
]

for url in urls:
    try:
        req = urllib.request.Request(url, method='HEAD')
        resp = urllib.request.urlopen(req, context=ctx)
        print(f"HTTP {resp.status} - {url}")
        print(f"  Content-Length: {resp.headers.get('Content-Length', 'N/A')}")
        print(f"  Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} - {url}")
    except Exception as e:
        print(f"ERROR - {url}: {e}")
