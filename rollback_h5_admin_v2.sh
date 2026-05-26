#!/usr/bin/env bash
# 回滚脚本（独立可用）
# 用法：bash rollback_h5_admin_v2.sh <h5|admin>

set -euo pipefail

SERVICE="${1:?missing service: h5 or admin}"
TOKEN="6b099ed3-7175-4a78-91f4-44570c84ed27"

case "$SERVICE" in
  h5)
    CONTAINER="${TOKEN}-h5"
    IMAGE_REPO="${TOKEN}-h5-web"
    CTNR_PORT="3001"
    NETWORK="${TOKEN}-network"
    ;;
  admin)
    CONTAINER="${TOKEN}-admin"
    IMAGE_REPO="${TOKEN}-admin-web"
    CTNR_PORT="3000"
    NETWORK="${TOKEN}_${TOKEN}-network"
    ;;
  *)
    echo "❌ unknown service: $SERVICE"; exit 1 ;;
esac

IMAGE_PREV="${IMAGE_REPO}:autodev-prev"

echo "⚠️  rollback $SERVICE -> $IMAGE_PREV"

# 校验 prev 镜像存在
if ! docker image inspect "$IMAGE_PREV" >/dev/null 2>&1; then
  echo "❌ no prev image $IMAGE_PREV; cannot rollback (this is likely the first deploy)"
  exit 2
fi

docker stop "$CONTAINER" 2>/dev/null || true
docker rm   "$CONTAINER" 2>/dev/null || true
docker run -d \
  --name "$CONTAINER" \
  --network "$NETWORK" \
  --restart unless-stopped \
  -e "PORT=$CTNR_PORT" \
  "$IMAGE_PREV"

echo "✅ rolled back to $IMAGE_PREV"
