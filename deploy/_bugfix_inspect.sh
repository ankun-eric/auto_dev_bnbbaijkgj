set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/
echo "=== pwd ==="
pwd
echo "=== top-level ls ==="
ls -la | head -40
echo "=== .git check ==="
ls -la .git 2>/dev/null | head -5 || echo "no .git"
echo "=== compose files ==="
ls -la docker-compose*.yml 2>/dev/null || echo "no compose yml here"
echo "=== docker ps for this project ==="
docker ps --filter name=6b099ed3-7175-4a78-91f4-44570c84ed27 --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
echo "=== find repo ==="
find /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/ -maxdepth 3 -name ".git" -type d 2>/dev/null | head -5
