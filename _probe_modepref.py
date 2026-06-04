import urllib.request, urllib.error
def call(method, body=None):
    try:
        req = urllib.request.Request('http://localhost:8000/api/user/mode-preference',
            data=body, headers={'Content-Type':'application/json'}, method=method)
        r = urllib.request.urlopen(req, timeout=5)
        print(method, '->', r.status, r.read()[:120])
    except urllib.error.HTTPError as e:
        print(method, '->', e.code, e.read()[:200])
    except Exception as e:
        print(method, 'ERR', e)
call('GET')
call('POST', b'{"mode":"care"}')
