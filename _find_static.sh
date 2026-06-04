echo '=== gateway nginx conf for this project ==='
docker exec gateway-nginx sh -c "grep -rl '6b099ed3' /etc/nginx/ 2>/dev/null"
echo '=== conf body ==='
docker exec gateway-nginx sh -c "cat \$(grep -rl '6b099ed3' /etc/nginx/conf.d/ 2>/dev/null | head -1)" 2>/dev/null | grep -iE 'location|proxy_pass|alias|root|miniprogram|download|static' | head -40
echo '=== existing mp zips on host ==='
ls -t /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/static/miniprogram/ 2>/dev/null | head -5
ls -dt /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/*static* 2>/dev/null
