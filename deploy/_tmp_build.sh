set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
echo "=== build backend + h5 + admin ==="
docker compose -f docker-compose.prod.yml build backend admin-web h5-web 2>&1 | tail -40
echo
echo "=== up ==="
docker compose -f docker-compose.prod.yml up -d backend admin-web h5-web 2>&1 | tail -20
echo
echo "=== status ==="
docker ps --format "table {{.Names}}\t{{.Status}}" | grep 6b099ed3
