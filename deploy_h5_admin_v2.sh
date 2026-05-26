#!/usr/bin/env bash
# =============================================================================
# Bug 修复 v1.0：H5/admin 容器单容器重建部署脚本
# 关键改造：
#   1. set -euo pipefail 杜绝静默失败
#   2. 镜像 tag 双轨：autodev-<GIT_SHA> + autodev-prev
#   3. 自检失败自动回滚到 prev
# 用法：bash deploy_h5_admin_v2.sh <GIT_SHA> <h5|admin>
# =============================================================================

set -euo pipefail

GIT_SHA="${1:?missing git sha}"
SERVICE="${2:?missing service: h5 or admin}"

# 部署唯一标识（项目 token，亦为 docker 网络/容器名前缀）
TOKEN="6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR="/home/ubuntu/${TOKEN}"
BASE_URL_PATH="/autodev/${TOKEN}"

# Next.js basePath 与 assetPrefix 均通过 build-arg 注入，未注入则 basePath="" → 全部 404
# 这是根因之一：原部署脚本如果遗漏 --build-arg，会构建出无 basePath 的镜像
case "$SERVICE" in
  h5)
    CONTAINER="${TOKEN}-h5"
    IMAGE_REPO="${TOKEN}-h5-web"
    CTNR_PORT="3001"
    CTX="${PROJECT_DIR}/h5-web"
    DOCKERFILE="${CTX}/Dockerfile"
    NETWORK="${TOKEN}-network"
    HEALTH_PATH="${BASE_URL_PATH}/health-profile/i-guard"
    BASE_PATH="${BASE_URL_PATH}"
    API_URL="${BASE_URL_PATH}/api"
    ;;
  admin)
    CONTAINER="${TOKEN}-admin"
    IMAGE_REPO="${TOKEN}-admin-web"
    CTNR_PORT="3000"
    CTX="${PROJECT_DIR}/admin-web"
    DOCKERFILE="${CTX}/Dockerfile"
    NETWORK="${TOKEN}_${TOKEN}-network"
    HEALTH_PATH="${BASE_URL_PATH}/admin/"
    # admin 的 nginx location 是 /autodev/{TOKEN}/admin/，所以 basePath 必须是 /autodev/{TOKEN}/admin
    BASE_PATH="${BASE_URL_PATH}/admin"
    API_URL="${BASE_URL_PATH}/api"
    ;;
  *)
    echo "❌ unknown service: $SERVICE"; exit 1 ;;
esac
BUILD_ARG_BASE="--build-arg NEXT_PUBLIC_BASE_PATH=${BASE_PATH} --build-arg NEXT_PUBLIC_API_URL=${API_URL}"

IMAGE_NEW="${IMAGE_REPO}:autodev-${GIT_SHA}"
IMAGE_PREV="${IMAGE_REPO}:autodev-prev"

# 通过 gateway 域名走 HTTPS（gateway 在 80 端口会 301 -> 443）
# 注意：必须用 -k 忽略证书校验、用 -L 跟随重定向，并断言最终 HTTP 200
HEALTH_DOMAIN="newbb.test.bangbangvip.com"
HEALTH_URL="https://${HEALTH_DOMAIN}${HEALTH_PATH}"

echo "============================================================"
echo "[deploy_h5_admin_v2] $(date '+%Y-%m-%d %H:%M:%S')"
echo "  SERVICE     = $SERVICE"
echo "  GIT_SHA     = $GIT_SHA"
echo "  CONTAINER   = $CONTAINER"
echo "  IMAGE_NEW   = $IMAGE_NEW"
echo "  IMAGE_PREV  = $IMAGE_PREV"
echo "  CTX         = $CTX"
echo "  NETWORK     = $NETWORK"
echo "  HEALTH_URL  = $HEALTH_URL"
echo "============================================================"

# ----- 步骤 1：保留当前 running 镜像为 prev -----
echo "[1/6] tag prev image"
IMAGE_RUNNING="$(docker inspect -f '{{.Config.Image}}' "$CONTAINER" 2>/dev/null || true)"
if [[ -n "$IMAGE_RUNNING" ]]; then
  docker tag "$IMAGE_RUNNING" "$IMAGE_PREV" || true
  echo "    prev image -> $IMAGE_RUNNING tagged as $IMAGE_PREV"
else
  echo "    no running image (first deploy); skip prev tag"
fi

# ----- 步骤 2：构建新镜像 -----
echo "[2/6] docker build -> $IMAGE_NEW"
echo "    BUILD_ARG: $BUILD_ARG_BASE"
# 不能用引号包裹 $BUILD_ARG_BASE，否则会被视作单一字符串
docker build $BUILD_ARG_BASE -t "$IMAGE_NEW" -f "$DOCKERFILE" "$CTX"

# ----- 步骤 3：停止并删除旧容器 -----
echo "[3/6] stop & rm old container"
docker stop "$CONTAINER" 2>/dev/null || true
docker rm   "$CONTAINER" 2>/dev/null || true

# ----- 步骤 4：启动新容器 -----
echo "[4/6] run new container on network=$NETWORK"
docker run -d \
  --name "$CONTAINER" \
  --network "$NETWORK" \
  --restart unless-stopped \
  -e "PORT=$CTNR_PORT" \
  "$IMAGE_NEW"

# ----- 步骤 5：健康自检（最多 90s）-----
# 注意：nginx 的 resolver valid=10s，容器重建后最多需要 ~10s 重新解析新容器 IP
# Next.js 启动后 trailing-slash 可能返回 308 重定向到带 / 的 URL；用 -L 跟随
echo "[5/6] health check (initial sleep 10s, then max 30 tries * 3s = 90s)"
sleep 10
HEALTH_OK=0
for i in $(seq 1 30); do
  HTTP_CODE=$(curl -k -L -sS -o /tmp/_health_${SERVICE}.html -w '%{http_code}' "$HEALTH_URL" 2>/dev/null || echo "000")
  if [[ "$HTTP_CODE" == "200" ]]; then
    echo "    ✅ HTTP $HTTP_CODE (try $i/30)"
    HEALTH_OK=1
    break
  fi
  echo "    waiting... HTTP=$HTTP_CODE (try $i/30)"
  sleep 3
done

if [[ "$HEALTH_OK" == "0" ]]; then
  echo "❌ health check failed after 60s, rolling back to $IMAGE_PREV"
  bash "$(dirname "$0")/rollback_h5_admin_v2.sh" "$SERVICE" || true
  exit 1
fi

echo "[6/6] ✅ deploy SUCCESS: $SERVICE -> $IMAGE_NEW"
