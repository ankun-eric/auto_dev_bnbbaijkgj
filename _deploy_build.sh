#!/bin/bash
set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27

echo "=== Step 5: 构建与启动 ==="
echo "=== 停止旧容器 ==="
docker compose -f docker-compose.prod.yml down 2>/dev/null || true

echo "=== 构建镜像 (build --pull) ==="
docker compose -f docker-compose.prod.yml build --pull || docker compose -f docker-compose.prod.yml build

echo "=== 启动容器 ==="
docker compose -f docker-compose.prod.yml up -d

echo "=== 等待容器健康检查通过 ==="
MAX_WAIT=24
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
  TOTAL=$(docker compose -f docker-compose.prod.yml ps -q 2>/dev/null | wc -l)
  HEALTHY=$(docker compose -f docker-compose.prod.yml ps --format json 2>/dev/null | grep -c '"Health":"healthy"' || echo 0)
  echo "  [$WAIT_COUNT/$MAX_WAIT] $HEALTHY/$TOTAL 容器已健康"
  if [ "$TOTAL" -gt 0 ] && [ "$HEALTHY" = "$TOTAL" ]; then
    echo "所有容器健康检查通过"
    break
  fi
  sleep 5
  WAIT_COUNT=$((WAIT_COUNT + 1))
done

echo "=== 将 gateway 加入新网络 ==="
docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network gateway-nginx 2>/dev/null || true

echo "=== 容器状态 ==="
docker compose -f docker-compose.prod.yml ps
