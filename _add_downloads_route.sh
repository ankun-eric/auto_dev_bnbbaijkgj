set -e
PID=6b099ed3-7175-4a78-91f4-44570c84ed27
CONF=/home/ubuntu/gateway/conf.d/${PID}.conf
echo "--- target host conf exists? ---"
ls -la "$CONF"
if grep -q "/autodev/${PID}/downloads/" "$CONF"; then
  echo "downloads route already exists"
else
  cp "$CONF" "${CONF}.bak_care_v4_$(date +%Y%m%d_%H%M%S)"
  awk -v pid="$PID" '
    $0 ~ ("^location /autodev/" pid "/ \\{") && !done {
      print "# [CARE-V4] 小程序代码包等静态下载（gateway 本地目录，不回源 h5）";
      print "location /autodev/" pid "/downloads/ {";
      print "    alias /data/static/apk/;";
      print "    default_type application/octet-stream;";
      print "    add_header Content-Disposition attachment;";
      print "}";
      print "";
      done=1;
    }
    { print }
  ' "$CONF" > "${CONF}.tmp" && mv "${CONF}.tmp" "$CONF"
  echo "--- inserted; show new downloads block ---"
  grep -n "downloads" "$CONF"
  echo "--- nginx -t ---"
  docker exec gateway-nginx nginx -t 2>&1 | tail -3
  echo "--- reload ---"
  docker exec gateway-nginx nginx -s reload 2>&1
  echo "reloaded"
fi
