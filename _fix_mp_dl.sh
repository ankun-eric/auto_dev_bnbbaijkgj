H5=6b099ed3-7175-4a78-91f4-44570c84ed27-h5
B=https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com
F=$(docker exec $H5 sh -c 'ls /app/public/downloads/ | head -1')
echo "zip in container: $F"
docker restart $H5 >/dev/null
sleep 6
echo "after restart, downloads path:"
curl -s -o /dev/null -w '%{http_code}\n' "$B/downloads/$F"
echo "logo still ok:"
curl -s -o /dev/null -w '%{http_code}\n' "$B/binni-xiaokang-logo.png"
