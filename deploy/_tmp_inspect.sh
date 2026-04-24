set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
echo "--- deploy dir ---"
ls deploy 2>/dev/null || echo "no deploy dir"
echo
echo "--- docker containers for this project ---"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "6b099ed3" || echo "no containers"
echo
echo "--- gateway nginx ---"
docker ps --format "{{.Names}}" | grep -i gateway || echo "no gateway"
echo
echo "--- compose files ---"
ls -la docker-compose*.yml 2>/dev/null || true
ls deploy/*.yml 2>/dev/null || true
ls deploy/*.yaml 2>/dev/null || true
echo
echo "--- project network ---"
docker network ls | grep 6b099ed3 || echo "no network"
