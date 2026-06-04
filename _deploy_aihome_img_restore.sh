#!/bin/bash
set -e
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJ="/home/ubuntu/${DEPLOY_ID}"
GW="gateway-nginx"

echo "=== 1. cd project & git pull ==="
cd "$PROJ"
git config --global --add safe.directory "$PROJ" 2>/dev/null || true
echo "--- before ---"; git log -1 --oneline || true
timeout 60 git fetch origin master --no-tags || { echo "git fetch failed"; exit 1; }
git reset --hard origin/master
git clean -fd -e .env -e .env.production -e .env.build || true
echo "--- after ---"; git log -1 --oneline

echo "=== 2. ensure .env BUILD_COMMIT ==="
BUILD_COMMIT=$(git log -1 --format="%H")
# preserve existing .env if present
if [ -f .env ]; then
  grep -v '^BUILD_COMMIT=' .env > .env.tmp 2>/dev/null || true
  mv .env.tmp .env 2>/dev/null || true
fi
echo "BUILD_COMMIT=$BUILD_COMMIT" >> .env
echo "BUILD_COMMIT=$BUILD_COMMIT"

echo "=== 3. rebuild h5-web (no-cache) ==="
docker compose -f docker-compose.prod.yml build --no-cache h5-web

echo "=== 4. recreate h5-web container ==="
docker compose -f docker-compose.prod.yml up -d h5-web

echo "=== 5. wait h5 ready ==="
for i in $(seq 1 24); do
  ST=$(docker inspect -f '{{.State.Status}}' ${DEPLOY_ID}-h5 2>/dev/null || echo none)
  if [ "$ST" = "running" ]; then echo "h5 running"; break; fi
  echo "waiting h5... ($ST) [$((i*5))s]"; sleep 5
done
docker ps --format '{{.Names}}\t{{.Status}}' | grep ${DEPLOY_ID} || true

echo "=== 6. reconnect gateway to network ==="
docker network connect ${DEPLOY_ID}-network ${GW} 2>/dev/null || echo "already connected"

echo "=== 7. gateway nginx test & reload ==="
docker exec ${GW} nginx -t && docker exec ${GW} nginx -s reload && echo "gateway reloaded"

echo "=== 8. internal smoke check ==="
docker exec ${GW} curl -sf -o /dev/null -w "h5 root http=%{http_code}\n" http://${DEPLOY_ID}-h5:3001/ || echo "internal h5 check failed"

echo "=== DEPLOY DONE ==="
