#!/usr/bin/env bash
set -e

C=6b099ed3-7175-4a78-91f4-44570c84ed27-backend

echo "=== env ==="
docker exec $C sh -c 'env | grep -iE "ROOT_PATH|API_BASE|BASE_URL" | head -20'

echo "=== probe inside container localhost:8000 various paths ==="
for P in "/" "/openapi.json" "/api/safety-rope/status" "/api/openapi.json" "/docs" "/api/docs"; do
  S=$(docker exec $C python3 -c "import urllib.request as u
try:
  r=u.urlopen('http://127.0.0.1:8000$P',timeout=5)
  print(r.status)
except Exception as e:
  print('ERR',e)
")
  echo "$P -> $S"
done

echo "=== app routes containing safety-rope ==="
docker exec $C python3 -c "
from app.main import app
paths = sorted([r.path for r in app.routes if hasattr(r,'path') and 'safety-rope' in r.path])
print('count=', len(paths))
for p in paths: print(' ', p)
"
