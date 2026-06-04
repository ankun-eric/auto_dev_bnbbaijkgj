#!/bin/bash
set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
C=6b099ed3-7175-4a78-91f4-44570c84ed27-backend
for f in backend/app/api/member_center_v2.py backend/app/api/membership.py backend/app/api/guardian_system_v12.py backend/app/api/ai_call.py backend/app/main.py backend/app/init_data.py backend/app/schemas/membership.py; do
  rel=${f#backend/}
  docker cp "$f" "$C:/app/$rel"
done
docker cp backend/tests/test_member_center_prd_v1_aligned.py $C:/app/tests/test_member_center_prd_v1_aligned.py
docker cp backend/tests/test_member_center_v2.py $C:/app/tests/test_member_center_v2.py
docker restart $C
sleep 6
docker exec $C grep -c 'free_quota' /app/app/api/member_center_v2.py
echo DONE
