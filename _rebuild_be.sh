cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
docker compose build backend 2>&1 | tail -20
docker compose up -d backend 2>&1 | tail -10
sleep 10
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend grep -c "BUGFIX-MY-GUARDIAN-CARD-2-20260528" /app/app/api/guardian_system_v13.py