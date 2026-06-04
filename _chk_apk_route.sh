echo "--- apk route conf ---"
docker exec gateway-nginx sh -c 'cat /etc/nginx/conf.d/gateway-routes/6b099ed3-7175-4a78-91f4-44570c84ed27-apk.conf'
echo "--- where apk files live on host (from alias/root) ---"
ls -la /home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/apk_download 2>/dev/null | head -5
