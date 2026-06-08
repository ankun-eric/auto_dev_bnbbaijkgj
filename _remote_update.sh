#!/bin/bash
set -e
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR="/home/ubuntu/${DEPLOY_ID}"
GIT_URL="https://kun-an:pt-djWjY3sqZzsvJ2nrhjV5e6mn_53e2cacd-e746-4659-8db4-024903ec9b74@codeup.aliyun.com/6a05a6159b7ce0afb00c035e/6b099ed3-7175-4a78-91f4-44570c84ed27.git"

echo "=== Step 1: Update code from git ==="
cd "${PROJECT_DIR}"

# Show current remotes
echo "Current remotes:"
git remote -v || true

# If origin doesn't exist or is wrong, set it
if ! git remote | grep -q 'origin'; then
    echo "Adding origin remote..."
    git remote add origin "${GIT_URL}"
else
    echo "Setting origin URL..."
    git remote set-url origin "${GIT_URL}"
fi

echo "Fetching from origin..."
git fetch --depth 1 origin master

echo "Resetting to origin/master..."
git reset --hard origin/master

echo "Current commit:"
git log --oneline -3

echo "=== Step 2: Rebuild containers ==="
cd "${PROJECT_DIR}"
docker compose -f docker-compose.prod.yml build --pull backend h5-web

echo "=== Step 3: Restart containers ==="
docker compose -f docker-compose.prod.yml up -d backend h5-web

echo "=== Step 4: Wait for healthy ==="
for i in $(seq 1 30); do
    sleep 10
    echo "Check $i..."
    docker ps --format 'table {{.Names}}\t{{.Status}}' | grep "${DEPLOY_ID}" || true
    if docker ps --format '{{.Names}} {{.Status}}' | grep "${DEPLOY_ID}-backend" | grep -q "Up"; then
        echo "Backend is up!"
        break
    fi
done

echo "=== Final Status ==="
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo "=== Done! ==="
