#!/usr/bin/env bash
set -eu
PROJ=/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
cd "$PROJ"

echo "=== STEP 1: backup old backend & h5-web dirs ==="
TS=$(date +%Y%m%d_%H%M%S)
if [ -d backend ]; then mv backend backend.bak_$TS; fi
if [ -d h5-web ]; then mv h5-web h5-web.bak_$TS; fi

echo "=== STEP 2: extract new backend & h5-web ==="
tar -xzf _bugfix_backend.tar.gz
tar -xzf _bugfix_h5web.tar.gz

echo "=== STEP 3: verify safety_rope code arrived ==="
grep -n "safety_rope" backend/app/main.py | head -5
grep -n "safety-rope-entry" h5-web/src/app/care-home/page.tsx | head -3

echo "=== STEP 4: docker compose build --no-cache backend h5-web ==="
docker compose -f docker-compose.yml build --no-cache backend h5-web

echo "=== STEP 5: recreate containers ==="
docker compose -f docker-compose.yml up -d --force-recreate backend h5-web

echo "=== STEP 6: wait for healthy ==="
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python3 -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/openapi.json',timeout=3).status)" 2>/dev/null | grep -q 200; then
    echo "[backend ready]"
    break
  fi
  echo "wait backend... ($i)"
  sleep 3
done

echo "=== STEP 7: verify safety_rope routes registered in OpenAPI ==="
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python3 -c "
import json, urllib.request
d = json.loads(urllib.request.urlopen('http://127.0.0.1:8000/openapi.json').read())
ps = sorted([p for p in d.get('paths',{}) if 'safety-rope' in p])
print('safety_rope_paths_count =', len(ps))
for p in ps: print(' ', p)
"

echo "=== STEP 8: tail backend logs for safety_rope errors ==="
docker logs --tail 40 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | grep -iE 'safety_rope|include_router|importerror|traceback' | tail -20 || echo "[no safety_rope errors]"

echo "=== DONE ==="
