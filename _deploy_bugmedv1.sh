#!/bin/bash
set -e
PROJ_DIR=/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
BE_CT=6b099ed3-7175-4a78-91f4-44570c84ed27-backend

# 1) 覆盖项目目录中的 backend 源文件
cp /tmp/bugmedv1/medication_plans_v1.py $PROJ_DIR/backend/app/api/medication_plans_v1.py
cp /tmp/bugmedv1/health_archive_v5.py   $PROJ_DIR/backend/app/api/health_archive_v5.py
cp /tmp/bugmedv1/medication_reminder.py $PROJ_DIR/backend/app/api/medication_reminder.py
cp /tmp/bugmedv1/test_bug_med_v1_20260521.py $PROJ_DIR/backend/tests/test_bug_med_v1_20260521.py
echo OK_COPY_HOST

# 2) docker cp 注入运行容器
docker cp /tmp/bugmedv1/medication_plans_v1.py $BE_CT:/app/app/api/medication_plans_v1.py
docker cp /tmp/bugmedv1/health_archive_v5.py   $BE_CT:/app/app/api/health_archive_v5.py
docker cp /tmp/bugmedv1/medication_reminder.py $BE_CT:/app/app/api/medication_reminder.py
docker cp /tmp/bugmedv1/test_bug_med_v1_20260521.py $BE_CT:/app/tests/test_bug_med_v1_20260521.py
echo OK_COPY_CONTAINER

# 3) 重启 backend
docker restart $BE_CT
echo OK_RESTART

# 4) 等待 backend 健康
for i in $(seq 1 30); do
  if docker exec $BE_CT curl -fsS http://localhost:8000/ >/dev/null 2>&1; then
    echo OK_BACKEND_READY_$i
    break
  fi
  sleep 2
done
