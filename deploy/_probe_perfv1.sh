PROJ=/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
echo "=== top-level listing ==="
ls -la $PROJ | head -40
echo ""
echo "=== looking for .git anywhere under proj ==="
find $PROJ -maxdepth 3 -name '.git' -type d 2>/dev/null | head
echo ""
echo "=== docker-compose files under proj ==="
find $PROJ -maxdepth 3 -name 'docker-compose*.yml' 2>/dev/null | head
echo ""
echo "=== running containers ==="
docker ps --format 'table {{.Names}}\t{{.Status}}' | head -40
echo ""
echo "=== docker networks ==="
docker network ls | grep -E '(6b099|gateway)' || true
