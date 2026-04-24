set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/
echo "=== remote file sanity check (must contain new logic) ==="
grep -n "merchant/m" h5-web/src/app/merchant/layout.tsx | head -5
grep -n "m/login" h5-web/src/app/merchant/m/login/page.tsx | head -5
grep -n "merchant" h5-web/src/lib/api.ts | head -10
grep -n "adminLoginUrl\|admin/login" admin-web/src/lib/api.ts | head -5
echo ""
echo "=== docker compose build --no-cache h5-web admin-web ==="
docker compose -f docker-compose.prod.yml build --no-cache h5-web admin-web 2>&1 | tail -80
echo ""
echo "=== docker compose up -d h5-web admin-web ==="
docker compose -f docker-compose.prod.yml up -d h5-web admin-web 2>&1 | tail -30
echo ""
echo "=== sleep 20 then ps ==="
sleep 20
docker ps --filter name=6b099ed3-7175-4a78-91f4-44570c84ed27 --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
