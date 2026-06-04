echo "--- gateway-nginx mounts ---"
docker inspect gateway-nginx --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} ({{.RW}}){{println}}{{end}}'
echo "--- host conf.d listing ---"
for d in /home/ubuntu/gateway-nginx /home/ubuntu/gateway /data/gateway-nginx /home/ubuntu/nginx; do
  [ -d "$d" ] && echo "FOUND $d" && ls -la "$d" 2>/dev/null | head
done
