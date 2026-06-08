#!/bin/bash
set -e
DEP_ID=6b099ed3-7175-4a78-91f4-44570c84ed27
DIR=/home/ubuntu/$DEP_ID
cd $DIR

echo "=== Rebuilding backend ==="
docker compose -f docker-compose.prod.yml build --pull backend 2>&1 || docker compose -f docker-compose.prod.yml build backend 2>&1

echo "=== Rebuilding h5 ==="
docker compose -f docker-compose.prod.yml build --pull h5 2>&1 || docker compose -f docker-compose.prod.yml build h5 2>&1

echo "=== Restarting containers ==="
docker compose -f docker-compose.prod.yml up -d backend h5

echo "=== Waiting for health ==="
for i in $(seq 1 20); do
  BOK=$(docker inspect ${DEP_ID}-backend --format '{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
  HOK=$(docker inspect ${DEP_ID}-h5 --format '{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
  echo "  [$i/20] backend=$BOK h5=$HOK"
  if [ "$BOK" = "healthy" ] && [ "$HOK" = "healthy" ]; then
    echo "All healthy!"
    break
  fi
  sleep 5
done

docker network connect ${DEP_ID}-network gateway-nginx 2>/dev/null || true
docker exec gateway-nginx nginx -s reload 2>/dev/null || true
echo "=== Done ==="
