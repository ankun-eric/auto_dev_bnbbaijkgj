#!/bin/bash
BASE="https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
echo "=== Frontend pages smoke ==="
for path in /member-center /my-coupons /unified-orders /admin/membership/free-quota /admin/users /admin/membership/plans; do
  code=$(curl -sL -o /dev/null -w "%{http_code}" "$BASE$path")
  echo "$path -> $code"
done
echo "=== Backend API smoke ==="
# Anonymous on protected endpoint should 401
for ep in /api/member/center /api/admin/membership/free-quota; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE$ep")
  echo "$ep (anon) -> $code"
done
# Health endpoint  
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/health" 2>/dev/null)
echo "/api/health -> $code"
echo DONE
