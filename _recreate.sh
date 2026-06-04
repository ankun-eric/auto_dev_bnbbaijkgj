#!/bin/bash
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
docker rm -f 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 6b099ed3-7175-4a78-91f4-44570c84ed27-admin || true
docker compose up -d h5-web admin-web
sleep 10
docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}'
echo "--- pages ---"
BASE="https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
for path in /member-center /my-coupons /unified-orders /admin/membership/free-quota /admin/users; do
  code=$(curl -sL -o /dev/null -w "%{http_code}" "$BASE$path")
  echo "$path -> $code"
done
echo "--- backend smoke ---"
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend grep -c 'free_quota' /app/app/api/member_center_v2.py
echo DONE
