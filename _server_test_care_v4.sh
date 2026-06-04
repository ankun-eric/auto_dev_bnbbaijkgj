cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
echo "===== RUN V4 TESTS IN BACKEND CONTAINER ====="
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python -m pytest tests/test_care_mode_optim_v4_20260531.py -q 2>&1 | tail -25
echo "===== BACKEND LOG TAIL ====="
docker logs --tail 15 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | tail -20
