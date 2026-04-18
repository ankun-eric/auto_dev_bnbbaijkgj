#!/bin/bash
set -e
PROJECT_DIR=/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
cd $PROJECT_DIR
echo "=== git pull ==="
git config --global --add safe.directory $PROJECT_DIR || true
git fetch --all 2>&1 | tail -5
git reset --hard origin/master 2>&1 | tail -5
git log -1 --oneline
echo "=== docker compose build & up (admin-web + h5-web + backend) ==="
docker compose -f docker-compose.prod.yml up -d --build backend admin-web h5-web 2>&1 | tail -40
echo "=== 容器状态 ==="
docker ps --filter "name=6b099ed3" --format "table {{.Names}}\t{{.Status}}"
