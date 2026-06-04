#!/bin/bash
set -e
PROJ=6b099ed3-7175-4a78-91f4-44570c84ed27
ROOT=/home/ubuntu/$PROJ
CONT_BE=${PROJ}-backend

cd $ROOT
echo "== copy backend files into container =="
docker cp $ROOT/backend/app/api/user_mode_preference.py ${CONT_BE}:/app/app/api/user_mode_preference.py
docker cp $ROOT/backend/app/main.py ${CONT_BE}:/app/app/main.py
docker cp $ROOT/backend/tests/test_user_mode_preference_h5_carefix.py ${CONT_BE}:/app/tests/test_user_mode_preference_h5_carefix.py
echo "== restart backend =="
docker restart ${CONT_BE}
sleep 5
echo "== backend logs (tail) =="
docker logs --tail 40 ${CONT_BE}
echo "== probe internal =="
docker exec ${CONT_BE} curl -sf -o /dev/null -w "GET / -> %{http_code}\n" http://localhost:8000/ || true
