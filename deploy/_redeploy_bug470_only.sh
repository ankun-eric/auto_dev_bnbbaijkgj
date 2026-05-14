#!/bin/bash
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27 || exit 1
echo "==== verify Bug-470 marker ===="
grep -c "Bug-470" backend/app/api/chat.py backend/app/main.py h5-web/src/components/ai-chat/ChatCards.tsx || true
echo "==== stop ===="
docker compose stop backend h5-web 2>&1 | tail -5
echo "==== rm ===="
docker compose rm -f backend h5-web 2>&1 | tail -5
echo "==== build ===="
docker compose build --no-cache backend h5-web 2>&1 | tail -200
echo "==== up ===="
docker compose up -d backend h5-web 2>&1 | tail -5
sleep 35
echo "==== status ===="
docker ps --format "{{.Names}} {{.Status}}" | grep 6b099ed3
echo "==== bug470 migrate log ===="
docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | grep -E "bug470|prompt_type_config" | tail -20
echo "==== latest backend errors ===="
docker logs --tail 80 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | grep -E "ERROR|Traceback|Error" | tail -20 || true
