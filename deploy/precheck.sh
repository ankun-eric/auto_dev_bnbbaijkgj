#!/bin/bash
echo '=== 磁盘空间检查 ==='
df -h / | tail -1

echo '=== Docker 状态 ==='
docker info 2>/dev/null | head -5 || echo 'Docker 未运行'

echo '=== Git 状态 ==='
git --version 2>/dev/null || echo 'Git 未安装'

echo '=== 网络检查（ACR 可达性）==='
curl -sI https://crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com/v2/ 2>&1 | head -3 || echo '无法访问 ACR'

echo '=== 已有项目目录检查 ==='
ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ 2>/dev/null || echo '项目目录不存在（首次部署）'

echo '=== 当前运行容器 ==='
docker ps -a --filter 'name=6b099ed3-7175-4a78-91f4-44570c84ed27-' --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' 2>/dev/null || echo '无相关容器'

echo '=== 获取当前运行容器的镜像 ID（用于后续备份） ==='
CURRENT_BACKEND_IMAGE_ID=$(docker inspect --format='{{.Image}}' 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>/dev/null || echo '')
CURRENT_FRONTEND_IMAGE_ID=$(docker inspect --format='{{.Image}}' 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 2>/dev/null || echo '')
CURRENT_ADMIN_IMAGE_ID=$(docker inspect --format='{{.Image}}' 6b099ed3-7175-4a78-91f4-44570c84ed27-admin 2>/dev/null || echo '')
echo "当前后端镜像 ID: $CURRENT_BACKEND_IMAGE_ID"
echo "当前H5前端镜像 ID: $CURRENT_FRONTEND_IMAGE_ID"
echo "当前Admin镜像 ID: $CURRENT_ADMIN_IMAGE_ID"

echo '=== PRE CHECK COMPLETE ==='
