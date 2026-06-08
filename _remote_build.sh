#!/bin/bash
set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
echo ===BUILD_BACKEND===
docker compose -f docker-compose.prod.yml build --pull backend 2>&1
echo ===BUILD_H5===
docker compose -f docker-compose.prod.yml build --pull h5-web 2>&1
echo ===BUILD_DONE===
