#!/bin/bash
set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/
DEPLOY_ID=6b099ed3-7175-4a78-91f4-44570c84ed27
VERSION_TAG=v20260608_101505

echo "=========================================="
echo "  开始 Docker 构建 - 版本: $VERSION_TAG"
echo "=========================================="

echo ""
echo "=== 构建后端镜像 ($DEPLOY_ID-backend) ==="
docker build -t ${DEPLOY_ID}-backend:${VERSION_TAG} -t ${DEPLOY_ID}-backend:latest -f ./backend/Dockerfile ./backend/ 2>&1
echo "后端镜像构建完成"

echo ""
echo "=== 构建管理后台镜像 ($DEPLOY_ID-admin-web) ==="
docker build -t ${DEPLOY_ID}-admin-web:${VERSION_TAG} -t ${DEPLOY_ID}-admin-web:latest -f ./admin-web/Dockerfile ./admin-web/ 2>&1
echo "管理后台镜像构建完成"

echo ""
echo "=== 构建H5前端镜像 ($DEPLOY_ID-h5-web) ==="
docker build -t ${DEPLOY_ID}-h5-web:${VERSION_TAG} -t ${DEPLOY_ID}-h5-web:latest -f ./h5-web/Dockerfile ./h5-web/ 2>&1
echo "H5前端镜像构建完成"

echo ""
echo "=== 构建完成，验证镜像 ==="
docker images --filter "reference=${DEPLOY_ID}-*" --format 'table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}'
echo ""
echo "BUILD_SUCCESS"
