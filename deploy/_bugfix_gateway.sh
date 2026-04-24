set -e
echo "=== gateway container ==="
GW=$(docker ps --format '{{.Names}}' | grep -i gateway | head -1)
echo "gateway: $GW"
echo "=== network connect ==="
docker network connect 6b099ed3-7175-4a78-91f4-44570c84ed27-network $GW 2>&1 || echo "(already connected or ok)"
echo "=== test h5 from gateway ==="
docker exec $GW wget -q -O- http://6b099ed3-7175-4a78-91f4-44570c84ed27-h5:3001/ -S --timeout=10 2>&1 | head -20 || echo "(h5 test done)"
echo "=== test admin from gateway ==="
docker exec $GW wget -q -O- http://6b099ed3-7175-4a78-91f4-44570c84ed27-admin:3000/ -S --timeout=10 2>&1 | head -10 || echo "(admin test done)"
echo "=== nginx reload ==="
docker exec $GW nginx -t 2>&1 || true
docker exec $GW nginx -s reload 2>&1 || true
