#!/bin/bash
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
echo "=== Building h5-web ==="
docker compose build h5-web 2>&1 | tail -20
echo "=== Building admin-web ==="
docker compose build admin-web 2>&1 | tail -20
echo "=== Recreate containers ==="
docker compose up -d h5-web admin-web 2>&1 | tail -10
sleep 5
docker ps --filter name=6b099ed3 --format '{{.Names}} {{.Status}}'
echo "=== H5 page test ==="
curl -s -o /dev/null -w 'h5 /member-center: %{http_code}\n' https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/member-center
curl -s -o /dev/null -w 'h5 /my-coupons: %{http_code}\n' https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/my-coupons
curl -s -o /dev/null -w 'h5 /unified-orders: %{http_code}\n' https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/unified-orders
echo "=== Admin page test ==="
curl -s -o /dev/null -w 'admin /membership/free-quota: %{http_code}\n' https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/membership/free-quota
echo DONE
