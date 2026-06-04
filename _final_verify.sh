#!/bin/bash
set -e
C=6b099ed3-7175-4a78-91f4-44570c84ed27-backend
echo "=== Install pytest in fresh container ==="
docker exec $C pip install pytest pytest-asyncio aiosqlite httpx -q 2>&1 | tail -5
echo "=== Run aligned member-center tests ==="
docker exec -w /app $C python -m pytest tests/test_member_center_prd_v1_aligned.py -v --tb=short 2>&1 | tail -30
echo "=== Run /api/member/center smoke (anonymous, should 401) ==="
curl -s -o /dev/null -w '/api/member/center (anon): %{http_code}\n' https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/member/center
echo "=== H5 page accessibility ==="
BASE="https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
for path in /member-center /my-coupons /unified-orders /admin/membership/free-quota; do
  code=$(curl -sL -o /dev/null -w "%{http_code}" "$BASE$path")
  echo "$path -> $code"
done
echo DONE
