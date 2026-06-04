#!/bin/bash
echo "=== host find prev zip ==="
find /home/ubuntu -name 'miniprogram_20260601_225607_3f7e.zip' 2>/dev/null | head
echo "=== gateway conf downloads ==="
docker exec gateway-nginx grep -rn "downloads" /etc/nginx/ 2>/dev/null | head
echo "=== gateway find prev zip in container ==="
docker exec gateway-nginx find / -name 'miniprogram_20260601_2256*' 2>/dev/null | head
echo "=== h5 conf downloads (next has no nginx; check H5 public/downloads) ==="
docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 find / -name 'miniprogram_*.zip' 2>/dev/null | head
echo "=== gateway full conf for project (downloads location) ==="
docker exec gateway-nginx sh -c 'cat /etc/nginx/conf.d/*.conf /etc/nginx/nginx.conf 2>/dev/null | grep -n "downloads" '
