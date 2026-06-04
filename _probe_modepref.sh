#!/bin/bash
PROJ=6b099ed3-7175-4a78-91f4-44570c84ed27
CONT=${PROJ}-backend
docker exec $CONT python - <<'PY'
import urllib.request, urllib.error
try:
    urllib.request.urlopen('http://localhost:8000/api/user/mode-preference', timeout=5)
    print("OK 200")
except urllib.error.HTTPError as e:
    print("GET /api/user/mode-preference ->", e.code)
except Exception as e:
    print("ERR", e)
try:
    req = urllib.request.Request('http://localhost:8000/api/user/mode-preference',
                                  data=b'{"mode":"care"}',
                                  headers={'Content-Type':'application/json'},
                                  method='POST')
    urllib.request.urlopen(req, timeout=5)
    print("OK POST 200")
except urllib.error.HTTPError as e:
    print("POST /api/user/mode-preference ->", e.code)
except Exception as e:
    print("ERR", e)
PY
