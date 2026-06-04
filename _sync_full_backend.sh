#!/bin/bash
set -e
C=6b099ed3-7175-4a78-91f4-44570c84ed27-backend
# Sync local backend/app to container
echo "=== Extract uploaded tarball ==="
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
tar -xzf /tmp/backend_app.tar.gz -C backend/
# Copy entire app/ and tests/ into container
docker cp backend/app $C:/app/
docker cp backend/tests $C:/app/
docker restart $C
sleep 8
echo "=== Verify ==="
docker exec $C grep -c 'free_quota' /app/app/api/member_center_v2.py
docker exec $C grep -c 'is_recommended' /app/app/models/membership_plan.py
docker exec -w /app $C pip install pytest pytest-asyncio aiosqlite httpx -q 2>&1 | tail -3
echo "=== Run aligned tests ==="
docker exec -w /app $C python -m pytest tests/test_member_center_prd_v1_aligned.py -v --tb=short -p no:warnings 2>&1 | tail -30
echo DONE
