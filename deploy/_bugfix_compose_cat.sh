cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/
echo "=== docker-compose.prod.yml ==="
cat docker-compose.prod.yml
echo ""
echo "=== check h5-web directory files ==="
ls h5-web/src/lib/api.ts h5-web/src/app/merchant/layout.tsx h5-web/src/app/merchant/m/login/page.tsx 2>&1
echo ""
echo "=== check admin-web ==="
ls admin-web/src/lib/api.ts 2>&1
