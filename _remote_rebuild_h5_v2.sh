#!/bin/bash
echo "[$(date)] start" > /tmp/h5_care_rebuild.log
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 || exit 1
echo "[$(date)] cd ok" >> /tmp/h5_care_rebuild.log
docker compose build h5-web >> /tmp/h5_care_rebuild.log 2>&1
echo "[$(date)] build done" >> /tmp/h5_care_rebuild.log
docker compose up -d h5-web >> /tmp/h5_care_rebuild.log 2>&1
echo "[$(date)] up done" >> /tmp/h5_care_rebuild.log
