#!/bin/bash
echo "=== downloads location block ==="
docker exec gateway-nginx sh -c "sed -n '55,80p' /etc/nginx/conf.d/6b099ed3-7175-4a78-91f4-44570c84ed27.conf"
echo "=== gateway mounts for /data/static ==="
docker inspect gateway-nginx --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}' | grep -i static
echo "=== host listing of mapped dir candidates ==="
ls -la /home/ubuntu/gateway/static/apk 2>/dev/null | tail -5
