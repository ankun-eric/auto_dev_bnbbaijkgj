echo "--- gateway conf files containing this PID ---"
docker exec gateway-nginx sh -c 'grep -rln "6b099ed3-7175-4a78-91f4-44570c84ed27" /etc/nginx/ 2>/dev/null'
echo "--- location blocks for this PID ---"
docker exec gateway-nginx sh -c 'grep -rn "6b099ed3-7175-4a78-91f4-44570c84ed27" /etc/nginx/ 2>/dev/null | grep -iE "location|downloads|proxy_pass" | head -60'
