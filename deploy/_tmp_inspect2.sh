set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
echo "=== docker-compose.prod.yml ==="
cat docker-compose.prod.yml
echo
echo "=== gateway nginx conf for this project ==="
docker exec gateway ls /etc/nginx/conf.d/ 2>/dev/null | head -30
echo "---"
docker exec gateway cat /etc/nginx/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf 2>/dev/null || echo "no conf file for this project"
