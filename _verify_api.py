import urllib.request, urllib.error, json

def check(url, method='GET', data=None):
    try:
        req = urllib.request.Request(url, data=data, method=method, headers={'Content-Type': 'application/json'})
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]
    except Exception as e:
        return 0, str(e)[:200]

# Test 1: guide-status GET should 404
code, body = check('http://localhost:8000/api/health/guide-status')
print(f'GET /api/health/guide-status: {code}')

# Test 2: guide-status POST should 404
code, body = check('http://localhost:8000/api/health/guide-status', method='POST', data=b'{"action":"skip"}')
print(f'POST /api/health/guide-status: {code}')

# Test 3: health-profile/self should 401 (needs auth)
code, body = check('http://localhost:8000/api/health-profile/self')
print(f'GET /api/health-profile/self: {code}')
if code == 401:
    print('  -> OK: endpoint exists, requires auth')
elif code == 200:
    print('  -> OK: endpoint works')
else:
    print(f'  -> WARNING: unexpected status')

# Test 4: /api/health should 200
code, body = check('http://localhost:8000/api/health')
print(f'GET /api/health: {code}')
