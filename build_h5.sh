#!/bin/bash
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
BUILD_COMMIT=$(git log -1 --format="%H")
echo "BUILD_COMMIT=$BUILD_COMMIT"
echo "BUILD_COMMIT=$BUILD_COMMIT" > /tmp/h5_build_commit.txt
docker compose -f docker-compose.prod.yml build --no-cache --build-arg BUILD_COMMIT="$BUILD_COMMIT" h5-web > /tmp/h5_build.log 2>&1
echo "BUILD_EXIT=$?" >> /tmp/h5_build.log
echo "BUILD_DONE" > /tmp/h5_build_done.txt
