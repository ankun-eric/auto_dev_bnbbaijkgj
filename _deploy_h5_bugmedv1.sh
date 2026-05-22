#!/bin/bash
set -e
PROJ_DIR=/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
cd $PROJ_DIR

# 1) 解压H5源码补丁覆盖
tar -xzf /tmp/h5_bugmedv1.tar.gz
echo OK_EXTRACT

# 2) 重新构建 h5 镜像（用现有 docker-compose）
docker compose build h5-web 2>&1 | tail -30
echo OK_BUILD

# 3) 重启 h5 容器
docker compose up -d h5-web
echo OK_UP

# 4) 等待健康
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/" 2>/dev/null)
  if [ "$code" = "200" ]; then
    echo "OK_H5_READY_${i}_code${code}"
    break
  fi
  sleep 3
done
