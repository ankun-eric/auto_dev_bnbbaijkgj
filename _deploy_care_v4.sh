set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
echo "===== BUILD backend + h5-web ====="
docker compose -f docker-compose.prod.yml build backend h5-web
echo "===== UP ====="
docker compose -f docker-compose.prod.yml up -d backend h5-web
echo "===== PS ====="
docker compose -f docker-compose.prod.yml ps
