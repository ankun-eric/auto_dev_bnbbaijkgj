set -e
sleep 20
echo "=== backend logs (last 40) ==="
docker logs --tail 40 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | tail -40
echo
echo "=== link check ==="
BASE=https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27
for p in \
  "/api/health" \
  "/api/merchant-categories" \
  "/api/auth/merchant-status" \
  "/merchant/login/" \
  "/merchant/dashboard/" \
  "/merchant/orders/" \
  "/merchant/verifications/" \
  "/merchant/reports/" \
  "/merchant/settlement/" \
  "/merchant/invoice/" \
  "/merchant/staff/" \
  "/merchant/store-settings/" \
  "/merchant/downloads/" \
  "/merchant/messages/" \
  "/admin/" \
  "/admin/merchant-categories/" \
  "/admin/admin-settlements/" \
  "/" ; do
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 20 "${BASE}${p}")
  echo "[$code] ${BASE}${p}"
done
