#!/bin/bash
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
echo "=== Build backend image ==="
docker compose build backend 2>&1 | tail -10
echo "=== Recreate backend ==="
docker rm -f 6b099ed3-7175-4a78-91f4-44570c84ed27-backend || true
docker compose up -d backend
sleep 10
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend grep -c 'free_quota' /app/app/api/member_center_v2.py
echo "--- aligned tests ---"
docker exec -w /app 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python -m pytest tests/test_member_center_prd_v1_aligned.py -v --tb=short 2>&1 | tail -20
echo DONE
