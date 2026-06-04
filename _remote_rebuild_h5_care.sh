#!/bin/bash
# 后台重建 H5 容器，加入新 care-ai-home 页面
set -e
echo "[$(date)] start rebuild" > /tmp/h5_care_rebuild.log
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c "cd /app && npx next build" >> /tmp/h5_care_rebuild.log 2>&1
echo "[$(date)] build done, restart" >> /tmp/h5_care_rebuild.log
docker restart 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 >> /tmp/h5_care_rebuild.log 2>&1
echo "[$(date)] restart done" >> /tmp/h5_care_rebuild.log
