set -e
BASE=https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27
echo "=== merchant categories (默认类别应已初始化) ==="
curl -sS "${BASE}/api/merchant-categories" | head -c 1000
echo
echo
echo "=== DB: merchant_categories ==="
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -N -e "USE bini_health; SELECT id, code, name, status FROM merchant_categories;" 2>/dev/null
echo
echo "=== DB: MerchantMemberRole enum ==="
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -N -e "USE bini_health; SHOW COLUMNS FROM merchant_store_memberships LIKE 'role';" 2>/dev/null
echo
echo "=== DB: 新表 ==="
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -N -e "USE bini_health; SHOW TABLES LIKE '%attach%'; SHOW TABLES LIKE '%settlement%'; SHOW TABLES LIKE '%invoice%'; SHOW TABLES LIKE '%export%';" 2>/dev/null
echo
echo "=== merchant_profiles.category_id ==="
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -N -e "USE bini_health; SHOW COLUMNS FROM merchant_profiles LIKE 'category_id';" 2>/dev/null
