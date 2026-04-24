set -e
cd /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27
for i in 1 2 3 4 5; do
  echo "--- try $i ---"
  if git fetch origin master; then
    echo "fetch ok"
    break
  fi
  sleep 3
done
git reset --hard origin/master
git log --oneline -3
echo "--- current files ---"
ls backend/app/api/merchant_v1.py && echo "merchant_v1.py OK"
ls h5-web/src/app/merchant/layout.tsx && echo "h5 merchant OK"
