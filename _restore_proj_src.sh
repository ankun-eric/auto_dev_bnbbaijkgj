set -e
PROJ=/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/backend
# 恢复项目源目录 main.py 为镜像原始版（之前被本地超前版污染）
cp /tmp/_orig_main.py $PROJ/app/main.py
grep -q care_card_v1 $PROJ/app/main.py || cat /tmp/_cc_block.txt >> $PROJ/app/main.py
echo "main.py care_card count: $(grep -c care_card_v1 $PROJ/app/main.py)"
echo "main.py lines: $(wc -l < $PROJ/app/main.py)"
# care_card_v1.py 与 home_safety_v1.py 已通过 docker cp 写入容器；同步项目源目录
docker cp 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/app/api/care_card_v1.py $PROJ/app/api/care_card_v1.py
docker cp 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/app/api/home_safety_v1.py $PROJ/app/api/home_safety_v1.py
docker cp 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:/app/tests/test_care_mode_optim_v1_20260531.py $PROJ/tests/test_care_mode_optim_v1_20260531.py
echo "project src restored"
docker rm -f tmpberecover >/dev/null 2>&1 || true
