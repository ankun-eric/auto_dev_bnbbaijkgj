set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/
echo "=== current branch ==="
git branch --show-current || true
echo "=== remote branches ==="
git remote -v
git fetch origin 2>&1 | tail -20
echo "=== before reset ==="
git log -1 --oneline
# 优先 master，其次 main
if git rev-parse --verify origin/master >/dev/null 2>&1; then
  BR=master
else
  BR=main
fi
echo "using branch: $BR"
git reset --hard origin/$BR
git clean -fd
echo "=== after reset ==="
git log -1 --oneline
echo "=== compose files ==="
ls -la docker-compose*.yml 2>/dev/null || ls -la *.yml
